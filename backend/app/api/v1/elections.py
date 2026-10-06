import uuid
from typing import AsyncGenerator, List
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.voting import Election, User, UserRole, VoterParticipation
from app.schemas.voting import (
    ElectionOut,
    ElectionResultOut,
    VoteRequest,
    VoteResponse,
)
from app.services.voting_service import VotingService


# Асинхронна сесія до бази даних
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


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
    """Отримати список усіх активних голосувань із відміткою, чи голосував студент."""
    result = await db.execute(
        select(Election).options(selectinload(Election.candidates))
    )
    elections = result.scalars().all()

    # Отримуємо ID виборів, де студент уже проголосував
    voted_res = await db.execute(
        select(VoterParticipation.election_id).where(
            VoterParticipation.user_id == current_user.id
        )
    )
    voted_election_ids = set(voted_res.scalars().all())

    response = []
    for el in elections:
        out = ElectionOut.model_validate(el)
        out.has_voted = el.id in voted_election_ids
        response.append(out)

    return response


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
    """Отримати результати після закриття виборів."""
    return await VotingService.get_results(db=db, election_id=election_id)