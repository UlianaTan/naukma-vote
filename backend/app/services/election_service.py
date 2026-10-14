"""Життєвий цикл голосування: запуск, закриття (вручну / за таймером),
публікація результатів. Усі операції ідемпотентні й виконуються під
блокуванням рядка голосування (SELECT ... FOR UPDATE).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.lifecycle import activation_problems, as_utc, can_transition, is_expired
from app.models.enums import AuditAction, ElectionStatus
from app.models.voting import Candidate, Election
from app.services.audit_service import record_audit
from app.services.tally_service import compute_tally, count_eligible

TRIGGER_MANUAL = "manual"
TRIGGER_TIMER = "timer"
TRIGGER_LAZY = "lazy"  # закриття «на льоту» при зверненні після ends_at


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Голосування не знайдено")


async def get_election_locked(
    db: AsyncSession, election_id: uuid.UUID, *, with_candidates: bool = False
) -> Election:
    """Читає голосування з ексклюзивним блокуванням рядка до кінця транзакції.

    Сесія запит-скоупна (новий об'єкт на кожен запит), тому stale-стан у
    identity map неможливий.
    """
    stmt = select(Election).where(Election.id == election_id).with_for_update()
    if with_candidates:
        stmt = stmt.options(selectinload(Election.candidates))
    election = (await db.execute(stmt)).scalar_one_or_none()
    if not election:
        raise _not_found()
    return election


async def activate_election(
    db: AsyncSession, election_id: uuid.UUID, actor_id: uuid.UUID
) -> tuple[Election, bool]:
    now = datetime.now(timezone.utc)
    election = await get_election_locked(db, election_id)

    if election.status == ElectionStatus.ACTIVE:
        await db.commit()  # знімаємо блокування; повторний запит — no-op
        return election, False
    if not can_transition(election.status, ElectionStatus.ACTIVE):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Голосування вже завершене й не може бути запущене повторно",
        )

    candidate_count = int(
        (await db.scalar(select(func.count(Candidate.id)).where(Candidate.election_id == election_id))) or 0
    )
    problems = activation_problems(
        candidate_count=candidate_count,
        eligible_count=await count_eligible(db, election_id),
        ends_at=election.ends_at,
        now=now,
    )
    if problems:
        raise HTTPException(
            status_code=422,
            detail="Голосування не готове до запуску: " + "; ".join(problems),
        )

    election.status = ElectionStatus.ACTIVE
    record_audit(
        db,
        action=AuditAction.ELECTION_ACTIVATED,
        actor_id=actor_id,
        election_id=election.id,
        details={"candidates": candidate_count, "starts_at": election.starts_at, "ends_at": election.ends_at},
    )
    await db.commit()
    return election, True


async def close_election(
    db: AsyncSession,
    election_id: uuid.UUID,
    actor_id: Optional[uuid.UUID],
    trigger: str = TRIGGER_MANUAL,
) -> tuple[Election, bool]:
    """Закриває голосування, фіксує підсумки в журналі.

    Рядок голосування блокується FOR UPDATE: поки закриття не завершене,
    нові голоси чекають (вони беруть FOR SHARE) і після закриття бачать CLOSED.
    Тому після commit кількість бюлетенів більше не змінюється.
    """
    election = await get_election_locked(db, election_id)

    if election.status == ElectionStatus.CLOSED:
        await db.commit()  # commit, не rollback: rollback експайрить об'єкт (MissingGreenlet)
        return election, False
    if not can_transition(election.status, ElectionStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Закрити можна лише запущене голосування",
        )

    tally = await compute_tally(db, election)
    election.status = ElectionStatus.CLOSED
    election.closed_at = datetime.now(timezone.utc)
    # У журнал — лише агрегати без розбивки по кандидатах і без переможця:
    # організатор і спостерігачі не мають бачити підсумок до публікації.
    record_audit(
        db,
        action=AuditAction.ELECTION_CLOSED,
        actor_id=actor_id,
        election_id=election.id,
        details={
            "trigger": trigger,
            "total_ballots": tally.ballots_total,
            "participants": tally.participants_count,
            "eligible": tally.eligible_count,
            "consistent": tally.consistent,
        },
    )
    await db.commit()
    return election, True


async def close_if_expired(db: AsyncSession, election_id: uuid.UUID) -> None:
    """Страховка поверх таймера: якщо час вийшов, закриваємо перед відповіддю."""
    row = (
        await db.execute(
            select(Election.status, Election.ends_at).where(Election.id == election_id)
        )
    ).first()
    if row and is_expired(row.status, row.ends_at, datetime.now(timezone.utc)):
        await close_election(db, election_id, None, TRIGGER_LAZY)


async def expired_election_ids(db: AsyncSession, now: Optional[datetime] = None) -> list[uuid.UUID]:
    now = as_utc(now or datetime.now(timezone.utc))
    res = await db.execute(
        select(Election.id)
        .where(Election.status == ElectionStatus.ACTIVE, Election.ends_at <= now)
        .order_by(Election.ends_at)
    )
    return list(res.scalars().all())


async def set_results_published(
    db: AsyncSession, election_id: uuid.UUID, actor_id: uuid.UUID, published: bool
) -> tuple[Election, bool]:
    election = await get_election_locked(db, election_id)
    if election.status != ElectionStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Результати можна публікувати лише після закриття голосування",
        )
    if bool(election.results_published) == published:
        await db.commit()
        return election, False

    election.results_published = published
    election.results_published_at = datetime.now(timezone.utc) if published else None
    record_audit(
        db,
        action=AuditAction.RESULTS_PUBLISHED if published else AuditAction.RESULTS_UNPUBLISHED,
        actor_id=actor_id,
        election_id=election.id,
    )
    await db.commit()
    return election, True