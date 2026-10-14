"""Чисті функції підрахунку: відсотки, переможець, нічия, нульова явка."""
from typing import Hashable, Mapping, Sequence, TypeVar

OUTCOME_NO_VOTES = "no_votes"
OUTCOME_WINNER = "winner"
OUTCOME_TIE = "tie"

K = TypeVar("K", bound=Hashable)


def percent(part: int, total: int) -> float:
    """Частка у відсотках з округленням до сотих; 0.0 якщо total <= 0."""
    if total <= 0:
        return 0.0
    return round(part * 100 / total, 2)


def determine_outcome(votes_by_candidate: Mapping[K, int]) -> tuple[str, list[K]]:
    """Визначає підсумок голосування.

    * жодного голосу (нульова явка) -> ("no_votes", []);
    * єдиний лідер -> ("winner", [id]);
    * кілька кандидатів з однаковим максимумом -> ("tie", [id, ...]).
    Система нічого не вирішує за організатора при нічиї: повертає всіх лідерів.
    """
    if not votes_by_candidate:
        return OUTCOME_NO_VOTES, []
    top = max(votes_by_candidate.values())
    if top <= 0:
        return OUTCOME_NO_VOTES, []
    leaders = [key for key, count in votes_by_candidate.items() if count == top]
    return (OUTCOME_WINNER if len(leaders) == 1 else OUTCOME_TIE), leaders


def sort_key(votes_count: int, name: str, candidate_id: object) -> tuple:
    """Стабільний порядок: більше голосів вище, далі за назвою, далі за id."""
    return (-votes_count, name.casefold(), str(candidate_id))


def sorted_rows(rows: Sequence[tuple[object, str, int]]) -> list[tuple[object, str, int]]:
    """rows: (candidate_id, name, votes_count)."""
    return sorted(rows, key=lambda r: sort_key(r[2], r[1], r[0]))