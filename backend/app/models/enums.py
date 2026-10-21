"""Спільні enum-и без залежностей від SQLAlchemy.

Винесені окремо, щоб доменна логіка (app/domain) імпортувалась і тестувалась
без ORM. Для зворотної сумісності їх повторно експортує app.models.voting.
Назви типів у PostgreSQL (electionstatus, userrole) не змінюються.
"""
import enum


class ElectionStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class UserRole(str, enum.Enum):
    VOTER = "voter"
    ADMIN = "admin"


class AuditAction(str, enum.Enum):
    """Дії адміністратора/системи, що потрапляють у журнал.

    У журнал НЕ потрапляють окремі голоси, факти явки конкретних людей та
    email-адреси: лише агрегати й службові ідентифікатори.
    """

    ELECTION_CREATED = "election.created"
    ELECTION_UPDATED = "election.updated"
    ELECTION_DELETED = "election.deleted"
    CANDIDATE_ADDED = "candidate.added"
    CANDIDATE_UPDATED = "candidate.updated"
    CANDIDATE_REMOVED = "candidate.removed"
    VOTERS_ADDED = "voters.added"
    VOTER_REMOVED = "voter.removed"
    ELECTION_ACTIVATED = "election.activated"
    ELECTION_CLOSED = "election.closed"
    RESULTS_PUBLISHED = "results.published"
    RESULTS_UNPUBLISHED = "results.unpublished"
    RESULTS_EXPORTED = "results.exported"