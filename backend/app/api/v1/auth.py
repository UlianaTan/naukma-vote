from fastapi import APIRouter, Depends, HTTPException, Response, Request, status, Cookie, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
import httpx
import urllib.parse

from app.database import get_db
from app.models.voting import User
from app.services.auth_service import create_refresh_token, verify_refresh_token, revoke_refresh_token
from app.core.cookies import set_session_cookie, set_session_cookies, set_csrf_cookie, clear_session_cookies
from app.core.jwt import create_access_token
from app.core.dependencies import get_current_user
from app.core.config import get_settings
from app.middleware.csrf import csrf_protect, logout_csrf_protect
from app.services.google_oauth import OAuthFailure, validate_profile, resolve_google_user

import uuid
import secrets

router = APIRouter()


@router.post("/login")
async def login(response: Response, db: AsyncSession = Depends(get_db), x_user_id: str | None = None):
    """Mock login for local development. Creates user if missing and issues tokens.
    Expects ALLOW_MOCK_AUTH=true for use.
    """
    settings = get_settings()
    if not settings.allow_mock_auth:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mock login disabled")

    user_uuid = uuid.UUID(str(x_user_id)) if x_user_id else uuid.UUID("a0000000-0000-0000-0000-000000000001")
    # ensure user exists
    q = await db.execute(select(User).where(User.id == user_uuid))
    user = q.scalar_one_or_none()
    if not user:
        user = User(id=user_uuid, email=f"user_{str(user_uuid)[:8]}@ukma.edu.ua")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access = create_access_token(str(user.id))
    refresh = await create_refresh_token(db, str(user.id))

    set_session_cookies(response, access, refresh)

    return {"status": "ok"}


def _frontend_target(target: str | None = None) -> str | None:
    origins = get_settings().frontend_origins
    for candidate in (target, *origins):
        if not candidate or "\\" in candidate or any(ord(c) < 32 for c in candidate):
            continue
        try:
            parsed = urllib.parse.urlsplit(candidate)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if parsed.scheme in {"http", "https"} and not parsed.username and not parsed.password and origin in origins:
                return candidate
        except ValueError:
            continue
    return None


def _clear_oauth(response: Response) -> Response:
    for name in ("oauth_state", "oauth_next"):
        response.delete_cookie(name, path="/", secure=get_settings().cookie_secure,
                               httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _oauth_error(code: str, target: str | None = None) -> Response:
    frontend = _frontend_target(target)
    if frontend:
        parsed = urllib.parse.urlsplit(frontend)
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/login",
                                      urllib.parse.urlencode({"error": code}), ""))
        response = RedirectResponse(url, status_code=303)
    else:
        response = JSONResponse({"detail": "Authentication is not configured"}, status_code=503)
    return _clear_oauth(response)


def _google_configured() -> bool:
    settings = get_settings()
    if not all(value.strip() for value in (settings.google_client_id, settings.google_client_secret,
                                           settings.google_redirect_uri)):
        return False
    try:
        uri = urllib.parse.urlsplit(settings.google_redirect_uri)
        return bool(uri.hostname and not uri.username and not uri.password and not uri.query and not uri.fragment
                    and uri.path == "/api/auth/google/callback"
                    and (uri.scheme == "https" or (settings.app_env == "local" and uri.scheme == "http"))
                    and _frontend_target() and len(settings.session_secret.encode()) >= 32
                    and settings.access_expires_seconds > 0 and settings.refresh_expires_seconds > 0
                    and settings.cookie_samesite)
    except ValueError:
        return False


@router.get("/google/login")
async def google_login(next: str | None = Query(None)):
    """Start a short-lived, browser-bound Google authorization attempt."""
    settings = get_settings()
    if not _google_configured():
        return _oauth_error("auth_unavailable")
    redirect_target = _frontend_target(next)
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email",
        "prompt": "select_account",
        "state": state,
    }
    if settings.allowed_email_domain:
        # A UI hint only; validate the returned Workspace membership below.
        params["hd"] = settings.allowed_email_domain
    url = httpx.URL("https://accounts.google.com/o/oauth2/v2/auth").copy_merge_params(params)
    response = RedirectResponse(str(url), status_code=303)
    for name, value in (("oauth_state", state), ("oauth_next", redirect_target)):
        response.set_cookie(name, value, path="/", httponly=True, samesite="lax",
                            secure=settings.cookie_secure, max_age=600)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/google/callback")
async def google_callback(code: str | None = None, state: str | None = None,
                          error: str | None = None, oauth_state: str | None = Cookie(None),
                          oauth_next: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    # Validate the browser binding even for provider errors. Never reflect error_description.
    if (not state or not oauth_state or len(state) > 256 or len(oauth_state) > 256
            or not secrets.compare_digest(state.encode(), oauth_state.encode())):
        return _oauth_error("invalid_state")
    if error:
        return _oauth_error("access_denied" if error == "access_denied" else "oauth_failed", oauth_next)
    if not code or len(code) > 4096:
        return _oauth_error("oauth_failed", oauth_next)
    if not _google_configured():
        return _oauth_error("auth_unavailable", oauth_next)
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={"code": code, "client_id": settings.google_client_id,
                      "client_secret": settings.google_client_secret,
                      "redirect_uri": settings.google_redirect_uri, "grant_type": "authorization_code"},
                headers={"Accept": "application/json"}, timeout=10.0,
            )
            if token_response.status_code != 200:
                raise OAuthFailure("google_unavailable" if token_response.status_code >= 500 else "oauth_failed")
            token_data = token_response.json()
            access = token_data.get("access_token") if isinstance(token_data, dict) else None
            if not isinstance(access, str) or not access:
                raise OAuthFailure("oauth_failed")
            profile_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access}"}, timeout=10.0,
            )
            if profile_response.status_code != 200:
                raise OAuthFailure("google_unavailable" if profile_response.status_code >= 500 else "oauth_failed")
            profile = profile_response.json()
            subject, email = validate_profile(profile, settings.allowed_email_domain)
            email_domain = email.rsplit("@", 1)[1]
            # Google is authoritative for Gmail and matching Workspace domains.
            # A third-party email_verified alone must not claim a legacy account.
            hosted_domain = profile.get("hd")
            link_legacy = email_domain == "gmail.com" or (
                isinstance(hosted_domain, str) and hosted_domain.lower() == email_domain
            )
    except httpx.RequestError:
        return _oauth_error("google_unavailable", oauth_next)
    except ValueError:
        return _oauth_error("oauth_failed", oauth_next)
    except OAuthFailure as exc:
        return _oauth_error(exc.code, oauth_next)
    try:
        user = await resolve_google_user(db, subject, email, link_legacy=link_legacy)
        access = create_access_token(str(user.id))
        refresh = await create_refresh_token(db, str(user.id))
    except OAuthFailure as exc:
        await db.rollback()
        return _oauth_error(exc.code, oauth_next)
    except SQLAlchemyError:
        await db.rollback()
        return _oauth_error("auth_unavailable", oauth_next)
    response = RedirectResponse(url=_frontend_target(oauth_next), status_code=303)
    set_session_cookies(response, access, refresh)
    return _clear_oauth(response)


@router.post("/refresh", dependencies=[Depends(csrf_protect)])
async def refresh(response: Response, refresh_token: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    rt = await verify_refresh_token(db, refresh_token)
    if not rt:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if not await db.get(User, rt.user_id):
        raise HTTPException(status_code=401, detail="User not found")
    # Issue new access token
    access = create_access_token(str(rt.user_id))
    set_session_cookie(response, "access_token", access, get_settings().access_expires_seconds)
    return {"status": "ok"}


@router.post("/logout", dependencies=[Depends(logout_csrf_protect)])
async def logout(response: Response, refresh_token: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)
    clear_session_cookies(response)
    return {"status": "ok"}


@router.get("/me")
async def me(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"id": str(user.id), "email": user.email, "role": user.role.value}


@router.get("/csrf")
async def csrf_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Bootstrap CSRF even when access expired; token is never an access credential."""
    response.headers["Cache-Control"] = "no-store"
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().frontend_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    refresh = await verify_refresh_token(db, request.cookies.get("refresh_token", ""))
    if not refresh or not await db.get(User, refresh.user_id):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    token = request.cookies.get("csrf_token")
    if token and len(token) > 256:
        token = None
    return {"csrf_token": set_csrf_cookie(response, token)}
