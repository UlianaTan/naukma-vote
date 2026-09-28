import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.voting import ElectionStatus

class CandidateCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="ПІБ кандидата")
    description: Optional[str] = Field(None, max_length=1000)

class CandidateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

class CandidateResponse(BaseModel):
    id: uuid.UUID
    election_id: uuid.UUID
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ElectionCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    starts_at: datetime
    ends_at: datetime
    candidates: Optional[List[CandidateCreate]] = []

    @model_validator(mode="after")
    def validate_dates(self):
        now = datetime.now(timezone.utc)
        if self.starts_at < now:
            raise ValueError("Час початку голосування не може бути в минулому")
        if self.ends_at <= self.starts_at:
            raise ValueError("Час завершення має бути строго пізнішим за час початку")
        return self

class ElectionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_update_dates(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("Час завершення має бути строго пізнішим за час початку")
        return self

class ElectionDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: ElectionStatus
    starts_at: datetime
    ends_at: datetime
    created_by: uuid.UUID
    candidates: List[CandidateResponse] = []

    model_config = ConfigDict(from_attributes=True)