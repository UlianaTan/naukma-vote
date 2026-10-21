"""Optional local-only Docker demo accounts; never provision accounts outside local."""
import os

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.core.config import get_settings
from app.database import AsyncSessionLocal
from app.models.enums import UserRole
from app.models.voting import User
from app.services.passwords import hash_password


def _account_config(prefix: str) -> tuple[str, str] | None:
    email = os.getenv(f"{prefix}_EMAIL", "").strip()
    password = os.getenv(f"{prefix}_PASSWORD", "")
    if not email and not password:
        return None
    if not email or not password:
        raise RuntimeError(f"Both {prefix}_EMAIL and {prefix}_PASSWORD must be configured")
    try:
        normalized_email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    except ValidationError:
        raise RuntimeError(f"{prefix}_EMAIL must be a valid email address") from None
    if len(normalized_email) > 255:
        raise RuntimeError(f"{prefix}_EMAIL must not exceed 255 characters")
    return normalized_email, password


async def provision_local_demo_accounts() -> None:
    if get_settings().app_env != "local":
        return

    admin = _account_config("LOCAL_ADMIN")
    test = _account_config("LOCAL_TEST")
    accounts = []
    if admin:
        accounts.append((admin, UserRole.ADMIN))
    if test:
        accounts.append((test, UserRole.VOTER))
    if not accounts:
        return

    prepared = [
        (email, hash_password(password), role)
        for (email, password), role in accounts
    ]
    async with AsyncSessionLocal() as db:
        for email, password_hash, role in prepared:
            user = await db.scalar(
                select(User).where(func.lower(func.ltrim(func.rtrim(User.email))) == email)
            )
            if user is not None:
                continue
            user = User(email=email, role=role, password_hash=password_hash)
            db.add(user)
        await db.commit()
