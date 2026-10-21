from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.cookies import (
    clear_session_cookies,
    set_csrf_cookie,
    set_session_cookie,
    set_session_cookies,
)
from app.core.dependencies import get_current_user
from app.core.jwt import create_access_token
from app.database import get_db
from app.middleware.csrf import csrf_protect
from app.models.enums import UserRole
from app.models.voting import User
from app.schemas.auth import LoginRequest, RegistrationRequest
from app.services.auth_service import (
    create_refresh_token,
    revoke_refresh_token,
    verify_refresh_token,
)
from app.services.passwords import hash_password, verify_password

router = APIRouter()


@router.post("/login")
async def login(
    credentials: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate an account and issue the standard session cookies."""
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().frontend_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    email = str(credentials.email).strip().lower()
    user = await db.scalar(
        select(User).where(func.lower(func.ltrim(func.rtrim(User.email))) == email)
    )
    valid_password = await run_in_threadpool(
        verify_password, credentials.password, user.password_hash if user else None
    )
    if not valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    access = create_access_token(str(user.id))
    refresh = await create_refresh_token(db, str(user.id))
    set_session_cookies(response, access, refresh)
    return {
        "status": "ok",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value,
        },
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    credentials: RegistrationRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().frontend_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")

    email = str(credentials.email).strip().lower()
    if not email.endswith("@ukma.edu.ua"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration is available only for @ukma.edu.ua email addresses",
        )
    existing = await db.scalar(
        select(User.id).where(func.lower(func.ltrim(func.rtrim(User.email))) == email)
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        email=email,
        role=UserRole.VOTER,
        password_hash=await run_in_threadpool(hash_password, credentials.password),
    )
    db.add(user)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from None

    access = create_access_token(str(user.id))
    refresh = await create_refresh_token(db, str(user.id))
    set_session_cookies(response, access, refresh)
    return {
        "status": "ok",
        "user": {"id": str(user.id), "email": user.email, "role": user.role.value},
    }


@router.post("/refresh", dependencies=[Depends(csrf_protect)])
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    rt = await verify_refresh_token(db, refresh_token)
    if not rt:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if not await db.get(User, rt.user_id):
        raise HTTPException(status_code=401, detail="User not found")
    access = create_access_token(str(rt.user_id))
    set_session_cookie(response, "access_token", access, get_settings().access_expires_seconds)
    return {"status": "ok"}


@router.post("/logout", dependencies=[Depends(csrf_protect)])
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)
    clear_session_cookies(response)
    return {"status": "ok"}


@router.get("/me")
async def me(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role.value,
    }


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
