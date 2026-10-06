import uuid
from typing import AsyncGenerator
from fastapi import HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.voting import User, UserRole

# Фіксований ID тестового адміністратора/організатора
ADMIN_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000000")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# Тимчасова mock-залежність до повної інтеграції з Auth-модулем
async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    """
    Повертає тестового адміністратора.
    Гарантує наявність запису в базі даних для валідності Election.created_by (Foreign Key).
    """
    res = await db.execute(select(User).where(User.id == ADMIN_USER_ID))
    user = res.scalar_one_or_none()

    if not user:
        user = User(
            id=ADMIN_USER_ID,
            email="organizer@ukma.edu.ua",
            role=UserRole.ADMIN,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def require_organizer(current_user: User = Depends(get_current_user)) -> User:
    """Перевіряє, що запит робить організатор голосування."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Дія дозволена виключно організаторам голосувань",
        )
    return current_user