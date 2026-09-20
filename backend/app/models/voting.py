import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ElectionStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class UserRole(str, enum.Enum):
    VOTER = "voter"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(Enum(UserRole), default=UserRole.VOTER, nullable=False)


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
    voted_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

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