import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.voting import ElectionStatus


class CandidateBase(BaseModel):
    name: str
    description: Optional[str] = None


class CandidateCreate(CandidateBase):
    pass


class CandidateOut(CandidateBase):
    id: uuid.UUID
    election_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class ElectionBase(BaseModel):
    title: str
    description: Optional[str] = None
    starts_at: datetime
    ends_at: datetime


class ElectionCreate(ElectionBase):
    candidates: List[CandidateCreate]


class ElectionOut(ElectionBase):
    id: uuid.UUID
    status: ElectionStatus
    has_voted: Optional[bool] = False
    results_published: bool = False
    closed_at: Optional[datetime] = None
    candidates: List[CandidateOut] = []

    model_config = ConfigDict(from_attributes=True)


class VoteRequest(BaseModel):
    candidate_id: uuid.UUID


class VoteResponse(BaseModel):
    status: str = "success"
    message: str = "Ваш голос успішно зараховано"


class CandidateResult(BaseModel):
    candidate_id: uuid.UUID
    name: str
    votes_count: int
    percent: float = 0.0


class ElectionResultOut(BaseModel):
    """Публічні агреговані результати (без персональних даних)."""

    election_id: uuid.UUID
    title: str
    total_votes: int
    # no_votes (нульова явка) | winner | tie
    outcome: str = "no_votes"
    winner_ids: List[uuid.UUID] = []
    closed_at: Optional[datetime] = None
    results: List[CandidateResult]


class TurnoutOut(BaseModel):
    """Явка відносно кола виборців. Без розбивки по кандидатах."""

    election_id: uuid.UUID
    eligible_count: int
    participants_count: int
    turnout_percent: float
    # Кількість бюлетенів збігається з кількістю фактів участі
    consistent: bool


class AdminElectionResultOut(ElectionResultOut):
    eligible_count: int
    participants_count: int
    turnout_percent: float
    consistent: bool
    results_published: bool


class WhitelistAddRequest(BaseModel):
    """Пакет email для списку виборців (пошкоджені рядки не валять увесь запит)."""

    emails: List[str] = Field(..., min_length=1, max_length=5000)