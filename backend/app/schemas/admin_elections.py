import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from app.models.voting import ElectionStatus

STRIP = ConfigDict(str_strip_whitespace=True)


class CandidateCreate(BaseModel):
    model_config = STRIP
    name: str = Field(..., min_length=2, max_length=255, description="ПІБ кандидата")
    description: Optional[str] = Field(None, max_length=1000)

class CandidateUpdate(BaseModel):
    model_config = STRIP
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

class CandidateResponse(BaseModel):
    id: uuid.UUID
    election_id: uuid.UUID
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ElectionCreate(BaseModel):
    model_config = STRIP
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    candidates: List[CandidateCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        names = [c.name.casefold() for c in self.candidates]
        if len(names) != len(set(names)):
            raise ValueError("Імена кандидатів у межах голосування мають бути унікальними")
        now = datetime.now(timezone.utc)
        if self.starts_at < now:
            raise ValueError("Час початку голосування не може бути в минулому")
        if self.ends_at <= self.starts_at:
            raise ValueError("Час завершення має бути строго пізнішим за час початку")
        return self

class ElectionUpdate(BaseModel):
    model_config = STRIP
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    starts_at: Optional[AwareDatetime] = None
    ends_at: Optional[AwareDatetime] = None

    @model_validator(mode="after")
    def validate_update_dates(self):
        for field in ("title", "starts_at", "ends_at"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} не може бути null")
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
    closed_at: Optional[datetime] = None
    results_published: bool = False
    results_published_at: Optional[datetime] = None
    candidates: List[CandidateResponse] = []

    model_config = ConfigDict(from_attributes=True)


class LifecycleResponse(BaseModel):
    """Результат зміни статусу/видимості. changed=false — повторний (ідемпотентний) запит."""

    id: uuid.UUID
    status: ElectionStatus
    closed_at: Optional[datetime] = None
    results_published: bool
    changed: bool


class VoterOut(BaseModel):
    id: uuid.UUID
    email: str

    model_config = ConfigDict(from_attributes=True)


class InvalidEmail(BaseModel):
    value: str
    reason: str


class VotersAddResponse(BaseModel):
    added: int
    already_present: int
    duplicates_in_request: int
    invalid: List[InvalidEmail] = []


class AuditLogOut(BaseModel):
    id: uuid.UUID
    election_id: Optional[uuid.UUID] = None
    actor_user_id: Optional[uuid.UUID] = None
    action: str
    details: dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntegrityIssueOut(BaseModel):
    severity: str
    code: str
    election_id: Optional[uuid.UUID] = None
    message: str


class IntegrityReport(BaseModel):
    ok: bool
    issues: List[IntegrityIssueOut]