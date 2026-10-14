import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.lifecycle import VotingWindow, voting_window
from app.domain.tally import percent
from app.models.voting import (
    Ballot,
    Candidate,
    Election,
    ElectionStatus,
    EligibleVoter,
    User,
    VoterParticipation,
)
from app.schemas.voting import (
    AdminElectionResultOut,
    CandidateResult,
    ElectionOut,
    ElectionResultOut,
    TurnoutOut,
)
from app.services.election_service import close_if_expired
from app.services.tally_service import TallyResult, compute_tally


def is_duplicate_vote_error(exc: IntegrityError) -> bool:
    """Inspect driver metadata, including SQLAlchemy's asyncpg wrapper."""
    error = exc.orig
    seen = set()
    sqlstate = None
    constraint = None
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        sqlstate = getattr(error, "sqlstate", None) or getattr(error, "pgcode", None) or sqlstate
        constraint = getattr(error, "constraint_name", None) or constraint
        error = getattr(error, "__cause__", None)
    return sqlstate == "23505" and constraint == "uq_user_election_vote"


def _email_key(user: User) -> str:
    """Whitelist зберігається в нижньому регістрі, порівнюємо так само."""
    return user.email.strip().lower()


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Голосування не знайдено")


def _to_public_result(tally: TallyResult) -> ElectionResultOut:
    return ElectionResultOut(
        election_id=tally.election_id,
        title=tally.title,
        total_votes=tally.total_votes,
        outcome=tally.outcome,
        winner_ids=tally.winner_ids,
        closed_at=tally.closed_at,
        results=[
            CandidateResult(
                candidate_id=cid,
                name=name,
                votes_count=count,
                percent=percent(count, tally.total_votes),
            )
            for cid, name, count in tally.rows
        ],
    )


class VotingService:

    @staticmethod
    async def cast_vote(
        db: AsyncSession,
        election_id: uuid.UUID,
        candidate_id: uuid.UUID,
        user: User,
    ) -> bool:
        # 1. Блокуємо рядок голосування в режимі FOR SHARE до кінця транзакції.
        #    Багато голосів проходять паралельно, але закриття (FOR UPDATE)
        #    чекає на всі голоси, що вже в роботі, а голоси, які прийшли після
        #    закриття, після очікування бачать статус CLOSED.
        result = await db.execute(
            select(Election)
            .where(Election.id == election_id)
            .with_for_update(read=True)
        )
        election = result.scalar_one_or_none()
        if not election:
            raise _not_found()

        # 2. Час фіксується ПІСЛЯ отримання блокування: голос, що чекав
        #    закриття, оцінюється вже за станом після нього.
        now = datetime.now(timezone.utc)
        if election.status != ElectionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Голосування наразі не активне або завершилось",
            )
        window = voting_window(election.starts_at, election.ends_at, now)
        if window == VotingWindow.NOT_STARTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Голосування ще не розпочалось",
            )
        if window == VotingWindow.ENDED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Голосування наразі не активне або завершилось",
            )

        # 3. Перевіряємо, чи кандидат належить до цих виборів
        cand_res = await db.execute(
            select(Candidate.id).where(
                Candidate.id == candidate_id,
                Candidate.election_id == election_id,
            )
        )
        if not cand_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Недійсний кандидат для цього голосування",
            )

        # 4. Перевіряємо whitelist (без урахування регістру)
        whitelist_res = await db.execute(
            select(EligibleVoter.id).where(
                EligibleVoter.election_id == election_id,
                func.lower(EligibleVoter.email) == _email_key(user),
            )
        )
        if not whitelist_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вас немає у списку виборців для цього голосування",
            )

        # 5. Швидка перевірка повторного голосу (остаточний захист — UNIQUE)
        already = await db.execute(
            select(VoterParticipation.id).where(
                VoterParticipation.election_id == election_id,
                VoterParticipation.user_id == user.id,
            )
        )
        if already.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ви вже проголосували в цьому голосуванні",
            )

        # 6. Атомарна транзакція: факт явки + анонімний бюлетень
        try:
            db.add(VoterParticipation(election_id=election_id, user_id=user.id))
            db.add(Ballot(election_id=election_id, candidate_id=candidate_id))
            await db.flush()
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()

            if is_duplicate_vote_error(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ви вже проголосували в цьому голосуванні",
                )

            # Інші помилки цілісності не маскуємо під повторний голос
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Помилка цілісності бази даних при збереженні голосу",
            )

        return True

    # ---- Перегляд для виборця ------------------------------------------------

    @staticmethod
    async def list_for_voter(db: AsyncSession, user: User) -> list[ElectionOut]:
        """Не-чернетки, до яких користувача допущено (за whitelist)."""
        result = await db.execute(
            select(Election)
            .options(selectinload(Election.candidates))
            .join(EligibleVoter, EligibleVoter.election_id == Election.id)
            .where(
                Election.status != ElectionStatus.DRAFT,
                func.lower(EligibleVoter.email) == _email_key(user),
            )
            .order_by(Election.starts_at.desc(), Election.id)
        )
        elections = result.scalars().all()

        voted_res = await db.execute(
            select(VoterParticipation.election_id).where(VoterParticipation.user_id == user.id)
        )
        voted_ids = set(voted_res.scalars().all())

        out_list = []
        for el in elections:
            out = ElectionOut.model_validate(el)
            out.has_voted = el.id in voted_ids
            out_list.append(out)
        return out_list

    @staticmethod
    async def get_for_voter(db: AsyncSession, election_id: uuid.UUID, user: User) -> ElectionOut:
        await close_if_expired(db, election_id)
        result = await db.execute(
            select(Election)
            .options(selectinload(Election.candidates))
            .where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()
        # Чернетки для виборців не існують
        if not election or election.status == ElectionStatus.DRAFT:
            raise _not_found()

        eligible = await db.execute(
            select(EligibleVoter.id).where(
                EligibleVoter.election_id == election_id,
                func.lower(EligibleVoter.email) == _email_key(user),
            )
        )
        if not eligible.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вас немає у списку виборців для цього голосування",
            )
        voted = await db.execute(
            select(VoterParticipation.id).where(
                VoterParticipation.election_id == election_id,
                VoterParticipation.user_id == user.id,
            )
        )
        out = ElectionOut.model_validate(election)
        out.has_voted = voted.scalar_one_or_none() is not None
        return out

    # ---- Результати ------------------------------------------------------------

    @staticmethod
    async def _load_closed(db: AsyncSession, election_id: uuid.UUID) -> Election:
        await close_if_expired(db, election_id)
        result = await db.execute(
            select(Election)
            .where(Election.id == election_id)
        )
        election = result.scalar_one_or_none()
        if not election or election.status == ElectionStatus.DRAFT:
            raise _not_found()
        return election

    @staticmethod
    async def get_results(db: AsyncSession, election_id: uuid.UUID) -> ElectionResultOut:
        """Публічні результати: лише закрите ТА опубліковане голосування."""
        election = await VotingService._load_closed(db, election_id)
        if election.status != ElectionStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Результати доступні лише після закриття голосування",
            )
        if not election.results_published:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Результати ще не опубліковані організатором",
            )
        return _to_public_result(await compute_tally(db, election))

    @staticmethod
    async def get_admin_tally(db: AsyncSession, election_id: uuid.UUID) -> tuple[Election, TallyResult]:
        """Підсумки для організатора: після закриття, незалежно від публікації."""
        election = await VotingService._load_closed(db, election_id)
        if election.status != ElectionStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Результати доступні лише після закриття голосування",
            )
        return election, await compute_tally(db, election)

    @staticmethod
    async def get_admin_results(db: AsyncSession, election_id: uuid.UUID) -> AdminElectionResultOut:
        election, tally = await VotingService.get_admin_tally(db, election_id)
        public = _to_public_result(tally)
        return AdminElectionResultOut(
            **public.model_dump(),
            eligible_count=tally.eligible_count,
            participants_count=tally.participants_count,
            turnout_percent=tally.turnout_percent,
            consistent=tally.consistent,
            results_published=bool(election.results_published),
        )

    @staticmethod
    async def get_turnout(db: AsyncSession, election_id: uuid.UUID) -> TurnoutOut:
        """Явка без розбивки по кандидатах — безпечна під час активного голосування."""
        await close_if_expired(db, election_id)
        exists = await db.scalar(select(Election.id).where(Election.id == election_id))
        if not exists:
            raise _not_found()
        # Один SQL-запит: усі counts бачать однаковий snapshot, навіть якщо
        # паралельний голос комітиться під час читання явки.
        counts = await db.execute(select(
            select(func.count(EligibleVoter.id))
            .where(EligibleVoter.election_id == election_id).scalar_subquery(),
            select(func.count(VoterParticipation.id))
            .where(VoterParticipation.election_id == election_id).scalar_subquery(),
            select(func.count(Ballot.id))
            .where(Ballot.election_id == election_id).scalar_subquery(),
        ))
        eligible, participants, ballots = counts.one()
        return TurnoutOut(
            election_id=election_id,
            eligible_count=eligible,
            participants_count=participants,
            turnout_percent=percent(participants, eligible),
            consistent=ballots == participants,
        )
