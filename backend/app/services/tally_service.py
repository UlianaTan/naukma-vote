"""Підрахунок результатів, явки та перевірка узгодженості даних."""
import uuid
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tally import determine_outcome, percent, sorted_rows
from app.models.voting import Ballot, Candidate, Election, EligibleVoter, VoterParticipation


@dataclass
class TallyResult:
    election_id: uuid.UUID
    title: str
    closed_at: Optional[datetime]
    rows: list[tuple[uuid.UUID, str, int]]  # (candidate_id, name, votes) відсортовані
    total_votes: int  # сума голосів за кандидатами цього голосування
    ballots_total: int  # усі бюлетені з election_id (для перевірки узгодженості)
    participants_count: int
    eligible_count: int
    outcome: str
    winner_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def turnout_percent(self) -> float:
        return percent(self.participants_count, self.eligible_count)

    @property
    def consistent(self) -> bool:
        """Бюлетенів стільки ж, скільки фактів участі, і всі належать кандидатам."""
        return self.ballots_total == self.participants_count == self.total_votes


async def _count(db: AsyncSession, stmt) -> int:
    return int((await db.scalar(stmt)) or 0)


async def count_eligible(db: AsyncSession, election_id: uuid.UUID) -> int:
    return await _count(
        db,
        select(func.count(EligibleVoter.id)).where(EligibleVoter.election_id == election_id),
    )


async def count_participants(db: AsyncSession, election_id: uuid.UUID) -> int:
    return await _count(
        db,
        select(func.count(VoterParticipation.id)).where(
            VoterParticipation.election_id == election_id
        ),
    )


async def count_ballots(db: AsyncSession, election_id: uuid.UUID) -> int:
    return await _count(
        db, select(func.count(Ballot.id)).where(Ballot.election_id == election_id)
    )


async def compute_tally(db: AsyncSession, election: Election) -> TallyResult:
    """Рахує голоси з бюлетенів. Викликається лише для закритого голосування
    (або під блокуванням рядка голосування в момент закриття)."""
    cand_res = await db.execute(
        select(Candidate.id, Candidate.name).where(Candidate.election_id == election.id)
    )
    candidates = [(row.id, row.name) for row in cand_res.all()]

    votes_res = await db.execute(
        select(Ballot.candidate_id, func.count(Ballot.id).label("cnt"))
        .where(Ballot.election_id == election.id)
        .group_by(Ballot.candidate_id)
    )
    votes = {row.candidate_id: int(row.cnt) for row in votes_res.all()}

    rows = sorted_rows([(cid, name, votes.get(cid, 0)) for cid, name in candidates])
    outcome, winners = determine_outcome({cid: count for cid, _, count in rows})

    return TallyResult(
        election_id=election.id,
        title=election.title,
        closed_at=election.closed_at,
        rows=rows,
        total_votes=sum(count for _, _, count in rows),
        ballots_total=await count_ballots(db, election.id),
        participants_count=await count_participants(db, election.id),
        eligible_count=await count_eligible(db, election.id),
        outcome=outcome,
        winner_ids=winners,
    )