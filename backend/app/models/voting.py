import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

from app.models.enums import AuditAction, ElectionStatus, UserRole  # noqa: F401

Base = declarative_base()


def utcnow() -> datetime:
    """Aware UTC (datetime.utcnow() повертає naive і залежить від TZ сервера)."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(Enum(UserRole), default=UserRole.VOTER, nullable=False)
    google_sub = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("google_sub", name="uq_users_google_sub"),
        Index("uq_users_email_normalized", func.lower(func.ltrim(func.rtrim(email))), unique=True),
    )


class Election(Base):
    __tablename__ = "elections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(ElectionStatus), default=ElectionStatus.DRAFT, nullable=False, index=True
    )
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # Тиждень 6: закриття, підрахунок і публікація результатів
    closed_at = Column(DateTime(timezone=True), nullable=True)
    results_published = Column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    results_published_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_elections_interval"),
        Index("ix_elections_status_ends_at", "status", "ends_at"),
    )

    candidates = relationship(
        "Candidate", back_populates="election", cascade="all, delete-orphan"
    )
    eligible_voters = relationship(
        "EligibleVoter", back_populates="election", cascade="all, delete-orphan"
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        UUID(as_uuid=True), ForeignKey("elections.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    election = relationship("Election", back_populates="candidates")


class EligibleVoter(Base):
    """Список дозволених email-адрес (whitelist) для конкретного голосування."""
    __tablename__ = "eligible_voters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        UUID(as_uuid=True), ForeignKey("elections.id"), nullable=False, index=True
    )
    email = Column(String(255), nullable=False)

    election = relationship("Election", back_populates="eligible_voters")

    __table_args__ = (
        UniqueConstraint("election_id", "email", name="uq_election_eligible_email"),
        CheckConstraint("email = lower(email)", name="ck_eligible_voters_email_lower"),
        Index("ix_eligible_voters_email", "email"),
    )


class VoterParticipation(Base):
    """Фіксація факту явки.

    Гарантує 1 голос на людину через UNIQUE constraint.
    НЕ містить інформації про те, за кого проголосували!
    """
    __tablename__ = "voter_participations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        UUID(as_uuid=True), ForeignKey("elections.id"), nullable=False, index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    voted_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("election_id", "user_id", name="uq_user_election_vote"),
    )


class Ballot(Base):
    """Анонімний бюлетень.

    Містить вибір, але НЕ містить user_id і точного часу голосування.
    """
    __tablename__ = "ballots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    election_id = Column(
        UUID(as_uuid=True), ForeignKey("elections.id"), nullable=False, index=True
    )
    candidate_id = Column(
        UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_ballots_election_candidate", "election_id", "candidate_id"),
    )


# Назва кандидата унікальна в межах голосування без урахування регістру
Index(
    "uq_candidates_election_name_lower",
    Candidate.election_id,
    func.lower(Candidate.name),
    unique=True,
)


class AuditLog(Base):
    """Append-only журнал дій організатора та системи.

    Без FK на elections: запис має пережити видалення чернетки.
    НЕ містить: окремих голосів, email виборців, фактів явки конкретних людей,
    результатів по кандидатах (лише агрегати). У PostgreSQL UPDATE/DELETE
    заборонені тригером (див. міграцію week9_data_integrity).
    """

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    election_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    actor_user_id = Column(UUID(as_uuid=True), nullable=True)  # NULL = система/таймер
    action = Column(String(64), nullable=False, index=True)
    details = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

class RefreshToken(Base):
    """Only SHA-256 digests of high-entropy refresh tokens are persisted."""
    __tablename__ = 'refresh_tokens'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
