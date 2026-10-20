"""Issue, validate and revoke opaque refresh tokens without storing their secrets."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.voting import RefreshToken


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_refresh_token(db: AsyncSession, user_id: str) -> str:
    lifetime = get_settings().refresh_expires_seconds
    if lifetime <= 0:
        raise ValueError('REFRESH_EXPIRES_SECONDS must be positive')
    token = secrets.token_urlsafe(48)
    db.add(RefreshToken(user_id=uuid.UUID(user_id), token_hash=_digest(token),
                        expires_at=datetime.now(timezone.utc) + timedelta(seconds=lifetime)))
    await db.commit()
    return token


async def verify_refresh_token(db: AsyncSession, token: str) -> RefreshToken | None:
    if not token or len(token) > 512:
        return None
    return await db.scalar(select(RefreshToken).where(
        RefreshToken.token_hash == _digest(token), RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > datetime.now(timezone.utc),
    ))


async def revoke_refresh_token(db: AsyncSession, token: str) -> None:
    if not token or len(token) > 512:
        return
    await db.execute(update(RefreshToken).where(
        RefreshToken.token_hash == _digest(token), RefreshToken.revoked_at.is_(None),
    ).values(revoked_at=datetime.now(timezone.utc)))
    await db.commit()
