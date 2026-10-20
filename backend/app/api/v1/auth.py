from fastapi import APIRouter, Depends, HTTPException, Response, status, Cookie, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
import urllib.parse

from app.database import get_db
from app.models.voting import User
from app.services.auth_service import create_refresh_token, verify_refresh_token, revoke_refresh_token
from app.core.jwt import create_access_token, decode_access_token
from app.core.config import get_settings
from app.middleware.csrf import csrf_protect

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

    # set cookies
    secure = settings.is_production
    response.set_cookie("access_token", access, httponly=True, samesite="lax", secure=secure)
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax", secure=secure)
    # csrf token (double-submit) — not httpOnly
    csrf = "csrf-" + str(uuid.uuid4())
    response.set_cookie("csrf_token", csrf, httponly=False, samesite="lax", secure=secure)

    return {"status": "ok"}


@router.get("/google/login")
async def google_login(next: str | None = Query(None)):
    """Redirects user to Google OAuth consent screen.

    Optional `next` param (frontend URL) will be used as post-login redirect.
    """
    settings = get_settings()
    if not settings.google_client_id or not settings.google_redirect_uri:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    # Determine redirect target after callback — must be one of configured frontend_origins
    frontend_origins = tuple(settings.frontend_origins)
    default_redirect = frontend_origins[0] if frontend_origins else "/"
    redirect_target = next or default_redirect
    # Validate redirect_target is allowed origin
    parsed = urllib.parse.urlparse(redirect_target)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    if origin not in frontend_origins:
        # fallback to default
        redirect_target = default_redirect

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = httpx.URL("https://accounts.google.com/o/oauth2/v2/auth").copy_merge_params(params)
    resp = RedirectResponse(str(url))
    # store state and next in short-lived cookies (httponly)
    secure = settings.is_production
    resp.set_cookie("oauth_state", state, httponly=True, samesite="lax", secure=secure)
    resp.set_cookie("oauth_next", redirect_target, httponly=True, samesite="lax", secure=secure)
    return resp


@router.get("/google/callback")
async def google_callback(code: str | None = None, state: str | None = None, oauth_state: str | None = Cookie(None), oauth_next: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    if not oauth_state or oauth_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    async with httpx.AsyncClient() as client:
        try:
            token_resp = await client.post(
                token_url,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
                timeout=10.0,
            )
        except Exception:
            raise HTTPException(status_code=502, detail="Failed to contact Google token endpoint")
    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")
    token_data = token_resp.json()
    access_token_google = token_data.get("access_token")
    if not access_token_google:
        raise HTTPException(status_code=400, detail="No access token from Google")

    # Fetch userinfo
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(userinfo_url, headers={"Authorization": f"Bearer {access_token_google}"}, timeout=10.0)
    if userinfo_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch userinfo from Google")
    userinfo = userinfo_resp.json()
    email = userinfo.get("email")
    email_verified = userinfo.get("email_verified", False)

    if not email or not email_verified:
        raise HTTPException(status_code=400, detail="Email not verified by Google")

    # Domain check
    allowed_domain = settings.allowed_email_domain
    if allowed_domain and "@" in email and email.split("@", 1)[1].lower() != allowed_domain.lower():
        raise HTTPException(status_code=403, detail="Email domain not allowed")

    # Lookup or create user
    try:
        res = await db.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        if not user:
            user = User(email=email)
            db.add(user)
            await db.commit()
            await db.refresh(user)
    except Exception:
        raise HTTPException(status_code=500, detail="Database error while creating user")

    # Issue our tokens and set cookies
    access = create_access_token(str(user.id))
    refresh = await create_refresh_token(db, str(user.id))

    # Determine redirect target (validate against allowed origins)
    redirect_target = oauth_next or (tuple(settings.frontend_origins)[0] if settings.frontend_origins else "/")
    parsed = urllib.parse.urlparse(redirect_target)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    frontend_origins = tuple(settings.frontend_origins)
    if origin not in frontend_origins:
        redirect_target = frontend_origins[0] if frontend_origins else "/"

    response = RedirectResponse(url=redirect_target)
    secure = settings.is_production
    response.set_cookie("access_token", access, httponly=True, samesite="lax", secure=secure)
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax", secure=secure)
    csrf = "csrf-" + str(secrets.token_urlsafe(16))
    response.set_cookie("csrf_token", csrf, httponly=False, samesite="lax", secure=secure)
    # Clear oauth_state and oauth_next cookies
    response.delete_cookie("oauth_state")
    response.delete_cookie("oauth_next")
    return response


@router.post("/refresh", dependencies=[Depends(csrf_protect)])
async def refresh(response: Response, refresh_token: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    rt = await verify_refresh_token(db, refresh_token)
    if not rt:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    # Issue new access token
    access = create_access_token(str(rt.user_id))
    response.set_cookie("access_token", access, httponly=True, samesite="lax", secure=get_settings().is_production)
    return {"status": "ok"}


@router.post("/logout", dependencies=[Depends(csrf_protect)])
async def logout(response: Response, refresh_token: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)
    # clear cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("csrf_token")
    return {"status": "ok"}


@router.get("/me")
async def me(access_token: str | None = Cookie(None), db: AsyncSession = Depends(get_db)):
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")
    try:
        payload = decode_access_token(access_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    user_id = uuid.UUID(payload["sub"])
    q = await db.execute(select(User).where(User.id == user_id))
    user = q.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return {"id": str(user.id), "email": user.email}
