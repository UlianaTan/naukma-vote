"""Фонове закриття голосувань за таймером.

Безпечно запускати в кількох процесах: кожне закриття ідемпотентне й іде під
блокуванням рядка (другий процес побачить CLOSED і нічого не зробить).
Коректність не залежить від таймера: голос після ends_at відхиляється самим
прийомом голосу, а звернення до результатів закриває прострочене голосування.
"""
import asyncio
import logging
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.election_service import TRIGGER_TIMER, close_election, expired_election_ids

logger = logging.getLogger("naukma.closer")


async def close_expired_once(session_factory: Callable[[], AsyncSession]) -> int:
    """Один прохід: закриває всі прострочені ACTIVE-голосування. Повертає кількість закритих."""
    async with session_factory() as db:
        ids = await expired_election_ids(db)
    closed = 0
    for election_id in ids:
        # Окрема сесія й транзакція на кожне голосування: збій одного не блокує решту
        async with session_factory() as db:
            try:
                _, changed = await close_election(db, election_id, None, TRIGGER_TIMER)
                closed += int(changed)
            except Exception as exc:  # noqa: BLE001 — цикл має жити далі
                logger.error("Не вдалося закрити голосування %s (%s)", election_id, type(exc).__name__)
                await db.rollback()
    return closed


async def run_closer_loop(
    session_factory: Callable[[], AsyncSession],
    interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    logger.info("Таймер закриття голосувань запущено (інтервал %.1f с)", interval_seconds)
    while not stop_event.is_set():
        try:
            closed = await close_expired_once(session_factory)
            if closed:
                logger.info("Закрито за таймером: %d", closed)
        except Exception as exc:  # noqa: BLE001
            logger.error("Збій проходу таймера закриття (%s)", type(exc).__name__)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
    logger.info("Таймер закриття голосувань зупинено")