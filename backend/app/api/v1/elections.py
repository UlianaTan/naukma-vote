import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.voting import User
from app.schemas.voting import (
    ElectionOut,
    ElectionResultOut,
    VoteRequest,
    VoteResponse,
)
from app.services.voting_service import VotingService


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