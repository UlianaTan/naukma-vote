import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr
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


class ElectionResultOut(BaseModel):
    election_id: uuid.UUID
    title: str
    total_votes: int
    results: List[CandidateResult]


class WhitelistAddRequest(BaseModel):
    emails: List[EmailStr]