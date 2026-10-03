import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.voting import (
    Ballot,
    Candidate,
    Election,
    ElectionStatus,
    EligibleVoter,
    User,
    VoterParticipation,
)
from app.schemas.voting import CandidateResult, ElectionResultOut


class VotingService:

    @staticmethod
    async def cast_vote(
        db: AsyncSession,
        election_id: uuid.UUID,
        candidate_id: uuid.UUID,
        user: User,
    ) -> bool:
        now = datetime.now(timezone.utc)

        # 1. Перевіряємо існування голосування
        result = await db.execute(
            select(Election).where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()
        if not election:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Голосування не знайдено",
            )

        # Безпечна нормалізація до UTC, щоб уникнути TypeError: can't compare offset-naive and offset-aware datetimes
        starts_at = (
            election.starts_at.replace(tzinfo=timezone.utc)
            if election.starts_at.tzinfo is None
            else election.starts_at
        )
        ends_at = (
            election.ends_at.replace(tzinfo=timezone.utc)
            if election.ends_at.tzinfo is None
            else election.ends_at
        )

        # 2. Перевіряємо статус і дедлайн
        if election.status != ElectionStatus.ACTIVE or not (
            starts_at <= now <= ends_at
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Голосування наразі не активне або завершилось",
            )

        # 3. Перевіряємо, чи кандидат належить до цих виборів
        cand_res = await db.execute(
            select(Candidate).where(
                Candidate.id == candidate_id,
                Candidate.election_id == election_id,
            )
        )
        if not cand_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недійсний кандидат для цього голосування",
            )

        # 4. Перевіряємо whitelist
        whitelist_res = await db.execute(
            select(EligibleVoter).where(
                EligibleVoter.election_id == election_id,
                EligibleVoter.email == user.email,
            )
        )
        if not whitelist_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вас немає у списку виборців для цього голосування",
            )

        # 5. Атомарна транзакція: факт явки + анонімний бюлетень
        try:
            participation = VoterParticipation(
                election_id=election_id, user_id=user.id
            )
            db.add(participation)

            ballot = Ballot(election_id=election_id, candidate_id=candidate_id)
            db.add(ballot)

            # Перехоплюємо UniqueConstraint при одночасному подвійному запиті
            await db.flush()
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ви вже проголосували в цьому голосуванні",
            )

        return True

    @staticmethod
    async def get_results(
        db: AsyncSession, election_id: uuid.UUID
    ) -> ElectionResultOut:
        result = await db.execute(
            select(Election)
            .options(selectinload(Election.candidates))
            .where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()
        if not election:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Голосування не знайдено",
            )

        if election.status != ElectionStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Результати доступні лише після закриття голосування",
            )

        votes_res = await db.execute(
            select(Ballot.candidate_id, func.count(Ballot.id).label("count"))
            .where(Ballot.election_id == election_id)
            .group_by(Ballot.candidate_id)
        )
        vote_counts = {row.candidate_id: row.count for row in votes_res.all()}

        results_list = []
        total_votes = 0
        for cand in election.candidates:
            count = vote_counts.get(cand.id, 0)
            total_votes += count
            results_list.append(
                CandidateResult(
                    candidate_id=cand.id, name=cand.name, votes_count=count
                )
            )

        return ElectionResultOut(
            election_id=election.id,
            title=election.title,
            total_votes=total_votes,
            results=results_list,
        )