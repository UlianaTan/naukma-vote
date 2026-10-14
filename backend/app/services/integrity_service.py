"""Перевірка цілісності даних (для релізу, QA після деплою та регулярного запуску).

Не виводить email, id користувачів чи вибір виборців: лише коди проблем,
id голосувань та кількості.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.lifecycle import as_utc
from app.models.enums import ElectionStatus
from app.models.voting import (
    Ballot,
    Candidate,
    Election,
    EligibleVoter,
    User,
    VoterParticipation,
)

CRITICAL = "critical"
WARNING = "warning"
# Скільки може «запізнюватись» таймер, перш ніж це стане попередженням
CLOSER_GRACE = timedelta(minutes=2)


@dataclass(frozen=True)
class IntegrityIssue:
    severity: str
    code: str
    message: str
    election_id: Optional[uuid.UUID] = None


async def validate_database(
    db: AsyncSession, election_id: Optional[uuid.UUID] = None
) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []
    now = datetime.now(timezone.utc)

    def scoped(stmt, column):
        return stmt.where(column == election_id) if election_id else stmt

    # 1. Кількість бюлетенів = кількість фактів участі
    ballots = dict(
        (await db.execute(scoped(
            select(Ballot.election_id, func.count(Ballot.id)).group_by(Ballot.election_id),
            Ballot.election_id))).all()
    )
    parts = dict(
        (await db.execute(scoped(
            select(VoterParticipation.election_id, func.count(VoterParticipation.id))
            .group_by(VoterParticipation.election_id),
            VoterParticipation.election_id))).all()
    )
    for eid in set(ballots) | set(parts):
        if ballots.get(eid, 0) != parts.get(eid, 0):
            issues.append(IntegrityIssue(
                CRITICAL, "BALLOTS_PARTICIPATIONS_MISMATCH",
                f"Бюлетенів {ballots.get(eid, 0)}, фактів участі {parts.get(eid, 0)}", eid))

    # 2. Бюлетень посилається на кандидата іншого голосування
    cross = await db.execute(scoped(
        select(Ballot.election_id, func.count(Ballot.id))
        .join(Candidate, Candidate.id == Ballot.candidate_id)
        .where(Candidate.election_id != Ballot.election_id)
        .group_by(Ballot.election_id), Ballot.election_id))
    for eid, cnt in cross.all():
        issues.append(IntegrityIssue(
            CRITICAL, "BALLOT_FOREIGN_CANDIDATE", f"{cnt} бюлетенів за кандидата чужого голосування", eid))

    # 3. Узгодженість статусів і службових полів
    elections = (await db.execute(scoped(select(Election), Election.id))).scalars().all()
    for el in elections:
        if el.status == ElectionStatus.CLOSED and el.closed_at is None:
            issues.append(IntegrityIssue(CRITICAL, "CLOSED_WITHOUT_TIMESTAMP", "Закрите голосування без closed_at", el.id))
        if el.status != ElectionStatus.CLOSED and el.closed_at is not None:
            issues.append(IntegrityIssue(CRITICAL, "CLOSED_AT_ON_OPEN_ELECTION", "closed_at заповнено для незакритого голосування", el.id))
        if el.results_published and el.status != ElectionStatus.CLOSED:
            issues.append(IntegrityIssue(CRITICAL, "PUBLISHED_BEFORE_CLOSE", "Результати опубліковані до закриття", el.id))
        if el.status == ElectionStatus.DRAFT and (ballots.get(el.id) or parts.get(el.id)):
            issues.append(IntegrityIssue(CRITICAL, "VOTES_IN_DRAFT", "Є голоси у чернетці", el.id))
        if el.status == ElectionStatus.ACTIVE and as_utc(el.ends_at) + CLOSER_GRACE < now:
            issues.append(IntegrityIssue(
                WARNING, "EXPIRED_NOT_CLOSED", "Час вийшов, але голосування досі active (перевірте таймер)", el.id))

    # 4. Участь людей поза whitelist (whitelist заморожений після старту)
    outside = await db.execute(scoped(
        select(VoterParticipation.election_id, func.count(VoterParticipation.id))
        .join(User, User.id == VoterParticipation.user_id)
        .outerjoin(EligibleVoter, and_(
            EligibleVoter.election_id == VoterParticipation.election_id,
            func.lower(EligibleVoter.email) == func.lower(User.email)))
        .where(EligibleVoter.id.is_(None))
        .group_by(VoterParticipation.election_id), VoterParticipation.election_id))
    for eid, cnt in outside.all():
        issues.append(IntegrityIssue(CRITICAL, "PARTICIPATION_OUTSIDE_WHITELIST", f"{cnt} учасників поза списком виборців", eid))

    # 5. Запущені/закриті голосування з менш ніж двома кандидатами
    few = await db.execute(scoped(
        select(Election.id, func.count(Candidate.id))
        .outerjoin(Candidate, Candidate.election_id == Election.id)
        .where(Election.status != ElectionStatus.DRAFT)
        .group_by(Election.id)
        .having(func.count(Candidate.id) < 2), Election.id))
    for eid, cnt in few.all():
        issues.append(IntegrityIssue(WARNING, "TOO_FEW_CANDIDATES", f"Лише {cnt} кандидат(ів) у запущеному голосуванні", eid))

    return issues