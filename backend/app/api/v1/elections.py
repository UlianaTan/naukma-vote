import uuid
from typing import List
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database import get_db
from app.models.voting import User, UserRole
from app.schemas.voting import (
    ElectionOut,
    ElectionResultOut,
    VoteRequest,
    VoteResponse,
)
from app.services.voting_service import VotingService


# Тестові профілі для перевірки допуску через заголовок X-User-Id
DEFAULT_TEST_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
STRANGER_TEST_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000002")

MOCK_USERS_REGISTRY = {
    DEFAULT_TEST_USER_ID: {
        "email": "test.student@ukma.edu.ua",
        "role": UserRole.VOTER,
    },
    STRANGER_TEST_USER_ID: {
        "email": "stranger@ukma.edu.ua",
        "role": UserRole.VOTER,
    },
}


# Тимчасова мок-авторизація для розробки та Swagger-тестування
async def get_current_user(
    x_user_id: str | None = Header(
        None,
        description="Mock User UUID для тестів допуску (за замовчуванням дефолтний студент)",
    ),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Повертає користувача для тестування.
    Отримує наявного або автоматично створює тестового користувача в БД,
    щоб забезпечити дійсний Foreign Key для VoterParticipation.
    """
    if not get_settings().allow_mock_auth:
        # У production mock вимкнено: цю залежність має замінити Auth-модуль
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Автентифікацію не налаштовано",
        )
    user_uuid = DEFAULT_TEST_USER_ID

    if x_user_id:
        try:
            user_uuid = uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Невалідний UUID у заголовку X-User-Id",
            )

    # 1. Перевіряємо, чи існує користувач у БД
    res = await db.execute(select(User).where(User.id == user_uuid))
    user = res.scalar_one_or_none()

    # 2. Якщо користувача немає — створюємо його в базі
    if not user:
        profile = MOCK_USERS_REGISTRY.get(
            user_uuid,
            {
                "email": f"user_{str(user_uuid)[:8]}@ukma.edu.ua",
                "role": UserRole.VOTER,
            },
        )
        user = User(
            id=user_uuid,
            email=profile["email"],
            role=profile["role"],
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


router = APIRouter(prefix="/elections", tags=["Elections & Voting Core"])


@router.get("", response_model=List[ElectionOut])
async def list_elections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Голосування (крім чернеток), до яких користувача допущено, з відміткою has_voted."""
    return await VotingService.list_for_voter(db, current_user)


@router.get("/{election_id}", response_model=ElectionOut)
async def get_election(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Деталі голосування та кандидати (404 для чернеток, 403 поза списком виборців)."""
    return await VotingService.get_for_voter(db, election_id, current_user)


@router.post(
    "/{election_id}/vote",
    response_model=VoteResponse,
    status_code=status.HTTP_200_OK,
)
async def vote(
    election_id: uuid.UUID,
    payload: VoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Віддати голос за кандидата."""
    await VotingService.cast_vote(
        db=db,
        election_id=election_id,
        candidate_id=payload.candidate_id,
        user=current_user,
    )
    return VoteResponse(
        status="success",
        message="Ваш голос успішно зараховано",
    )


@router.get("/{election_id}/results", response_model=ElectionResultOut)
async def get_results(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Агреговані результати: лише після закриття та публікації організатором."""
    return await VotingService.get_results(db=db, election_id=election_id)