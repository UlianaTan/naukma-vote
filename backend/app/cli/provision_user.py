"""Create or activate a user without exposing public self-registration."""
import argparse
import asyncio
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database import AsyncSessionLocal
from app.models.enums import UserRole
from app.models.voting import User
from app.services.passwords import hash_password


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision or reset a NaUKMA Vote account; passwords are entered interactively."
    )
    parser.add_argument("email", help="Account email address")
    parser.add_argument("--role", choices=[role.value for role in UserRole])
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email.strip())).lower()
    except ValidationError:
        raise SystemExit("Invalid email address") from None
    if len(email) > 255:
        raise SystemExit("Email address must not exceed 255 characters")

    allowed_domain = get_settings().allowed_email_domain
    if allowed_domain and email.rsplit("@", 1)[1] != allowed_domain:
        raise SystemExit(f"Email must use the configured @{allowed_domain} domain")

    password = getpass("Password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    try:
        hashed = hash_password(password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    role = UserRole(args.role) if args.role else None
    created = asyncio.run(_provision_hash(email, hashed, role))
    print(f"Account {'created' if created else 'updated'}: {email}")


async def provision_user(
    db: AsyncSession,
    email: str,
    password_hash: str,
    role: UserRole | None = None,
) -> bool:
    user = await db.scalar(
        select(User).where(func.lower(func.ltrim(func.rtrim(User.email))) == email)
    )
    created = user is None
    if created:
        user = User(email=email, role=role or UserRole.VOTER)
        db.add(user)
    elif role is not None:
        user.role = role
    user.password_hash = password_hash
    await db.commit()
    return created


async def _provision_hash(
    email: str, password_hash: str, role: UserRole | None
) -> bool:
    async with AsyncSessionLocal() as db:
        return await provision_user(db, email, password_hash, role)


if __name__ == "__main__":
    main()
