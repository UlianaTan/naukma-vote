"""Перевірка цілісності даних у БД (read-only).

Запуск з каталогу backend:
    python -m app.cli.validate_data              # усі голосування
    python -m app.cli.validate_data <election_id>  # одне голосування

Код виходу: 0 — критичних проблем немає, 1 — є критичні, 2 — помилка запуску.
Виводить лише коди проблем, id голосувань і кількості (без email/голосів).
"""
import asyncio
import sys
import uuid

from app.database import AsyncSessionLocal, engine
from app.services.integrity_service import CRITICAL, validate_database


async def _run(election_id):
    try:
        async with AsyncSessionLocal() as db:
            return await validate_database(db, election_id)
    finally:
        await engine.dispose()


def main(argv: list[str]) -> int:
    election_id = None
    if len(argv) > 1:
        try:
            election_id = uuid.UUID(argv[1])
        except ValueError:
            print("Невалідний election_id", file=sys.stderr)
            return 2
    try:
        issues = asyncio.run(_run(election_id))
    except Exception as exc:  # noqa: BLE001
        print(f"Помилка перевірки: {type(exc).__name__}", file=sys.stderr)
        return 2

    for issue in issues:
        print(f"[{issue.severity.upper()}] {issue.code} election={issue.election_id}: {issue.message}")
    critical = sum(1 for i in issues if i.severity == CRITICAL)
    print(f"Перевірено. Критичних: {critical}, попереджень: {len(issues) - critical}")
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))