import uuid
from typing import AsyncGenerator, List
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.voting import Election, User, VoterParticipation
from app.schemas.voting import (
    ElectionOut,
    ElectionResultOut,
    VoteRequest,
    VoteResponse,
)
from app.services.voting_service import VotingService


# Реальна асинхронна сесія до вашої бази даних Neon
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# Мок-авторизація з можливістю тестувати різних юзерів через Swagger/Postman
async def get_current_user(
    x_user_id: str | None = Header(
        None, description="Mock User UUID для тестів (за замовчуванням дефолтний студент)"
    ),
) -> User:
    if not x_user_id:
        return User(
            id=uuid.UUID("a0000000-0000-0000-0000-000000000001"),
            email="test.student@ukma.edu.ua",
        )
    try:
        user_uuid = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невалідний UUID у заголовку X-User-Id",
        )
    return User(
        id=user_uuid,
        email="test.student@ukma.edu.ua",
        is_admin=False,
    )


router = APIRouter(prefix="/elections", tags=["Elections & Voting Core"])


@router.get("", response_model=List[ElectionOut])
async def list_elections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отримати список усіх активних голосувань із відміткою, чи голосував студент."""
    # Підтягуємо кандидатів через selectinload, щоб уникнути MissingGreenlet при формуванні схем
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