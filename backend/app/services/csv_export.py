"""Агрегований CSV-експорт результатів (лише підсумки, без персональних даних)."""
import csv
import io
from typing import Any, Iterable, Mapping

CSV_COLUMNS = (
    "election_id",
    "candidate_id",
    "candidate_name",
    "votes",
    "percent_of_votes",
    "total_votes",
    "eligible_voters",
    "participants",
    "turnout_percent",
)

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
UTF8_BOM = "\ufeff"  # щоб Excel правильно відкрив кирилицю


def sanitize_cell(value: Any) -> str:
    """Захист від CSV/formula injection: назва кандидата не має виконуватись у Excel."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def build_results_csv(rows: Iterable[Mapping[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow(
            [
                sanitize_cell(row[column]) if column == "candidate_name" else row[column]
                for column in CSV_COLUMNS
            ]
        )
    return UTF8_BOM + buffer.getvalue()