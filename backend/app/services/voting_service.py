import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.voting import (
    Election,
    Candidate,
    EligibleVoter,
    VoterParticipation,
    Ballot,
    ElectionStatus,
    User,
)
from app.schemas.voting import ElectionResultOut, CandidateResult


class VotingService:

    @staticmethod
    async def cast_vote(
        db: AsyncSession, election_id: uuid.UUID, candidate_id: uuid.UUID, user: User
    ):
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

        # 2. Перевіряємо статус і дедлайн
        if election.status != ElectionStatus.ACTIVE or not (
            election.starts_at <= now <= election.ends_at
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Голосування наразі не активне або завершилось",
            )

        # 3. Перевіряємо, чи кандидат належить до цих виборів
        cand_res = await db.execute(
            select(Candidate).where(
                Candidate.id == candidate_id, Candidate.election_id == election_id
            )
        )
        if not cand_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недійсний кандидат для цього голосування",
            )

        # 4. Перевіряємо whitelist (чи входить студент у список голосуючих)
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

        # 5. Атомарна транзакція: фіксуємо факт явки та кладемо анонімний бюлетень
        try:
            # Фіксація явки
            participation = VoterParticipation(
                election_id=election_id, user_id=user.id
            )
            db.add(participation)

            # Анонімний бюлетень (жодного user_id!)
            ballot = Ballot(election_id=election_id, candidate_id=candidate_id)
            db.add(ballot)

            # Робимо flush, щоб перехопити колізію UniqueConstraint при спробі подвійного кліку
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

        # Агрегований підрахунок голосів через GROUP BY
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