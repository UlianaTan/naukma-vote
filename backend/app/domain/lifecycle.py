"""Чисті правила життєвого циклу голосування (без БД і без FastAPI).

Усі функції приймають `now` явно, тому поведінку на межах інтервалів
(голос на останній секунді) можна перевірити детермінованими тестами.

Прийнята семантика інтервалу: [starts_at, ends_at).
  * голос рівно в starts_at приймається;
  * голос рівно в ends_at вже НЕ приймається (голосування закрите);
  * момент прийняття — це час обробки запиту сервером під блокуванням рядка
    голосування, а не час, коли запит надіслав клієнт.
"""
import enum
from datetime import datetime, timezone
from typing import Optional

from app.models.enums import ElectionStatus

# Мінімум кандидатів для старту: з одним варіантом вибору немає.
MIN_CANDIDATES_TO_ACTIVATE = 2

ALLOWED_TRANSITIONS: dict[ElectionStatus, frozenset[ElectionStatus]] = {
    ElectionStatus.DRAFT: frozenset({ElectionStatus.ACTIVE}),
    ElectionStatus.ACTIVE: frozenset({ElectionStatus.CLOSED}),
    ElectionStatus.CLOSED: frozenset(),
}


class VotingWindow(str, enum.Enum):
    NOT_STARTED = "not_started"
    OPEN = "open"
    ENDED = "ended"


def as_utc(value: datetime) -> datetime:
    """Нормалізує datetime до aware UTC (SQLite повертає naive значення)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def voting_window(starts_at: datetime, ends_at: datetime, now: datetime) -> VotingWindow:
    start, end, current = as_utc(starts_at), as_utc(ends_at), as_utc(now)
    if current < start:
        return VotingWindow.NOT_STARTED
    if current >= end:
        return VotingWindow.ENDED
    return VotingWindow.OPEN


def is_voting_open(
    status: ElectionStatus, starts_at: datetime, ends_at: datetime, now: datetime
) -> bool:
    return (
        status == ElectionStatus.ACTIVE
        and voting_window(starts_at, ends_at, now) == VotingWindow.OPEN
    )


def is_expired(status: ElectionStatus, ends_at: datetime, now: datetime) -> bool:
    """ACTIVE-голосування, час якого вийшов, але яке ще не закрите таймером."""
    return status == ElectionStatus.ACTIVE and as_utc(now) >= as_utc(ends_at)


def can_transition(current: ElectionStatus, target: ElectionStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def activation_problems(
    *,
    candidate_count: int,
    eligible_count: int,
    ends_at: datetime,
    now: datetime,
    min_candidates: Optional[int] = None,
) -> list[str]:
    """Повертає список причин, чому чернетку ще не можна запускати."""
    required = MIN_CANDIDATES_TO_ACTIVATE if min_candidates is None else min_candidates
    problems: list[str] = []
    if candidate_count < required:
        problems.append(
            f"Потрібно щонайменше {required} кандидати (зараз {candidate_count})"
        )
    if eligible_count < 1:
        problems.append("Список виборців порожній")
    if as_utc(ends_at) <= as_utc(now):
        problems.append("Час завершення голосування вже минув")
    return problems