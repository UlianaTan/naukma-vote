import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.voting import (
    ElectionOut,
    VoteRequest,
    VoteResponse,
    ElectionResultOut,
)
from app.models.voting import Election, VoterParticipation, User
from app.services.voting_service import VotingService

# Заглушка залежності авторизації (яку передасть Backend Auth)
async def get_current_user() -> User:
    # Тимчасовий мок до інтеграції Google OAuth
    return User(
        id=uuid.UUID("a0000000-0000-0000-0000-000000000001"),
        email="test.student@ukma.edu.ua",
    )

# Залежність сесії БД
async def get_db() -> AsyncSession:
    raise NotImplementedError("Підключіть вашу AsyncSession з database.py")

router = APIRouter(prefix="/elections", tags=["Elections & Voting Core"])


@router.get("", response_model=List[ElectionOut])
async def list_elections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отримати список усіх активних голосувань із відміткою, чи голосував студент."""
    result = await db.execute(select(Election))
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
    return VoteResponse()


@router.get("/{election_id}/results", response_model=ElectionResultOut)
async def get_results(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отримати результати після закриття виборів."""
    return await VotingService.get_results(db=db, election_id=election_id)