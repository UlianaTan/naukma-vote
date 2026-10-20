"""Google profile validation and conflict-safe linking to local users."""
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.models.voting import User


class OAuthFailure(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_profile(profile: object, allowed_domain: str) -> tuple[str, str]:
    if not isinstance(profile, dict) or profile.get("email_verified") is not True:
        raise OAuthFailure("unverified_email")
    email = profile.get("email")
    subject = profile.get("sub")
    if not isinstance(email, str) or not isinstance(subject, str) or not subject or len(subject) > 255:
        raise OAuthFailure("invalid_profile")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(email.strip())).lower()
    except ValidationError:
        raise OAuthFailure("invalid_profile") from None
    if len(email) > 255:
        raise OAuthFailure("invalid_profile")
    if allowed_domain:
        hosted_domain = profile.get("hd")
        if (email.rsplit("@", 1)[1] != allowed_domain
                or not isinstance(hosted_domain, str) or hosted_domain.lower() != allowed_domain):
            raise OAuthFailure("invalid_domain")
    return subject, email


async def resolve_google_user(
    db: AsyncSession, subject: str, email: str, *, link_legacy: bool = False,
) -> User:
    # Retry unique-key races after rollback; never overwrite another Google identity.
    for _ in range(3):
        try:
            user = await db.scalar(select(User).where(User.google_sub == subject))
            email_users = list((await db.scalars(select(User).where(
                func.lower(func.trim(User.email)) == email).limit(2))).all())
            if len(email_users) > 1:
                raise OAuthFailure("account_conflict")
            email_user = email_users[0] if email_users else None
            if user:
                if email_user and email_user.id != user.id:
                    raise OAuthFailure("account_conflict")
                user.email = email
            elif email_user:
                # Only link legacy accounts without a Google identity. The caller has
                # already verified both email ownership and Workspace membership.
                if email_user.google_sub == subject:
                    # Another callback may have finished after our first lookup.
                    user = email_user
                    user.email = email
                elif email_user.google_sub is not None:
                    raise OAuthFailure("account_conflict")
                else:
                    if not link_legacy:
                        raise OAuthFailure("account_conflict")
                    user_id = email_user.id
                    claimed = await db.execute(update(User).where(
                        User.id == user_id, User.google_sub.is_(None)
                    ).values(google_sub=subject, email=email))
                    if claimed.rowcount != 1:
                        await db.rollback()
                        continue
                    user = email_user
            else:
                user = User(email=email, google_sub=subject)
                db.add(user)
            await db.commit()
            await db.refresh(user)
            return user
        except IntegrityError:
            await db.rollback()
    raise OAuthFailure("account_conflict")
