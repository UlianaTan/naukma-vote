from fastapi import HTTPException, status, Depends
from app.models.voting import User, UserRole

# Тимчасова mock-залежність до повної інтеграції з Auth-модулем
async def get_current_user() -> User:
    return User(
        email="organizer@ukma.edu.ua",
        role=UserRole.ADMIN
    )

async def require_organizer(current_user: User = Depends(get_current_user)) -> User:
    """Перевіряє, що запит робить організатор голосування."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Дія дозволена виключно організаторам голосувань"
        )
    return current_user