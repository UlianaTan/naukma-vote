"""Read-only database readiness; schema changes belong exclusively to Alembic."""
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models.voting import Base


class SchemaNotReady(RuntimeError):
    pass


def check_connection_schema(connection: Connection) -> None:
    scripts = ScriptDirectory(str(Path(__file__).resolve().parents[2] / "alembic"))
    expected = set(scripts.get_heads())
    actual = set(MigrationContext.configure(connection).get_current_heads())
    if actual != expected:
        raise SchemaNotReady("Схема БД не оновлена. Перевірте alembic current і виконайте alembic upgrade head перед запуском.")
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in tables:
            raise SchemaNotReady("Відсутні необхідні таблиці. Перевірте схему БД; не використовуйте stamp навмання.")
        columns = {column["name"] for column in inspector.get_columns(table.name)}
        if not set(table.columns.keys()) <= columns:
            raise SchemaNotReady("Відсутні необхідні колонки. Перевірте схему БД; не використовуйте stamp навмання.")


async def verify_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.run_sync(check_connection_schema)
