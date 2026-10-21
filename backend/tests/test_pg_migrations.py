"""Full migration chain on disposable PostgreSQL 18 schemas, including legacy data."""
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.test_pg_concurrency import validate_test_database_url
from app.core.schema import check_connection_schema
from app.models.voting import User, Election, Candidate, EligibleVoter, Ballot, VoterParticipation
from app.models.enums import UserRole

URL = os.getenv("TEST_DATABASE_URL")


@unittest.skipUnless(URL, "TEST_DATABASE_URL не задано")
class PostgreSQLMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        validate_test_database_url(URL)
        self.schema = "migration_test_" + uuid.uuid4().hex
        self.admin = create_async_engine(URL, hide_parameters=True)
        async with self.admin.begin() as connection:
            version = await connection.scalar(text("SHOW server_version_num"))
            self.assertEqual(int(version) // 10000, 18, "Migration tests require PostgreSQL 18")
            await connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_async_engine(URL, hide_parameters=True,
            connect_args={"server_settings": {"search_path": self.schema}})
        self.addAsyncCleanup(self.cleanup)

    async def cleanup(self):
        await self.engine.dispose()
        async with self.admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        await self.admin.dispose()

    def run_alembic(self, connection, action, target=None):
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
        config.attributes["connection"] = connection
        if target is None:
            action(config)
        else:
            action(config, target)

    async def upgrade(self, target="head"):
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda c: self.run_alembic(c, command.upgrade, target))

    async def test_empty_database_full_chain_matches_models_and_repeat_is_safe(self):
        await self.upgrade()
        await self.upgrade()
        async with self.engine.begin() as connection:
            await connection.run_sync(check_connection_schema)
            await connection.run_sync(lambda c: self.run_alembic(c, command.check))
            # The append-only audit trigger exists on migrated PostgreSQL, unlike create_all fixtures.
            trigger = await connection.scalar(text(
                "SELECT count(*) FROM pg_trigger WHERE tgname='trg_audit_logs_append_only' "
                "AND tgrelid='audit_logs'::regclass"))
            self.assertEqual(trigger, 1)

    async def test_upgrade_preserves_users_ownership_candidates_votes_and_participation(self):
        await self.upgrade("15533011651c")
        ids = {name: uuid.uuid4() for name in ("user", "election", "candidate", "voter", "ballot", "participation")}
        now = datetime.now(timezone.utc)
        async with self.engine.begin() as connection:
            await connection.execute(User.__table__.insert().values(
                id=ids["user"], email=" Existing@ukma.edu.ua ", role=UserRole.VOTER))
            await connection.execute(text(
                "INSERT INTO elections (id,title,status,starts_at,ends_at,created_by) "
                "VALUES (:id,'Legacy election','CLOSED',:start,:end,:owner)"),
                {"id": ids["election"], "start": now - timedelta(hours=2),
                 "end": now - timedelta(hours=1), "owner": ids["user"]})
            await connection.execute(Candidate.__table__.insert().values(
                id=ids["candidate"], election_id=ids["election"], name="Legacy candidate"))
            await connection.execute(EligibleVoter.__table__.insert().values(
                id=ids["voter"], election_id=ids["election"], email="EXISTING@ukma.edu.ua"))
            await connection.execute(Ballot.__table__.insert().values(
                id=ids["ballot"], election_id=ids["election"], candidate_id=ids["candidate"]))
            await connection.execute(VoterParticipation.__table__.insert().values(
                id=ids["participation"], election_id=ids["election"], user_id=ids["user"], voted_at=now))
        await self.upgrade()
        async with self.engine.begin() as connection:
            user = (await connection.execute(select(User.__table__))).mappings().one()
            self.assertEqual(user["id"], ids["user"])
            self.assertEqual(user["email"], "existing@ukma.edu.ua")
            self.assertIsNone(user["google_sub"])
            election = (await connection.execute(select(Election.__table__))).mappings().one()
            self.assertEqual(election["created_by"], ids["user"])
            self.assertFalse(election["results_published"])
            for model, name in ((Candidate, "candidate"), (EligibleVoter, "voter"),
                    (Ballot, "ballot"), (VoterParticipation, "participation")):
                self.assertEqual(await connection.scalar(select(model.id)), ids[name])
            self.assertEqual(await connection.scalar(select(EligibleVoter.email)), "existing@ukma.edu.ua")
            await connection.run_sync(check_connection_schema)
            await connection.run_sync(lambda c: self.run_alembic(c, command.check))

    async def test_conflicting_legacy_accounts_stop_upgrade_without_partial_schema_changes(self):
        await self.upgrade("8e4c2a7b9d10")
        async with self.engine.begin() as connection:
            for email in ("A@ukma.edu.ua", "a@ukma.edu.ua"):
                await connection.execute(User.__table__.insert().values(id=uuid.uuid4(), email=email, role=UserRole.VOTER))
        with self.assertRaisesRegex(RuntimeError, "Conflicting normalized"):
            await self.upgrade()
        async with self.engine.connect() as connection:
            self.assertEqual(await connection.scalar(text("SELECT version_num FROM alembic_version")), "8e4c2a7b9d10")
            columns = await connection.run_sync(lambda c: inspect(c).get_columns("users"))
            self.assertNotIn("google_sub", {column["name"] for column in columns})
            self.assertEqual(await connection.scalar(text("SELECT count(*) FROM users")), 2)
