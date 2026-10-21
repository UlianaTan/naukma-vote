"""Startup and readiness must never create or repair a database implicitly."""
import io
import logging
import os
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import deployment_problems, get_settings
from app.core.logging import PrivacyFilter, configure_private_logging
from app.core.schema import SchemaNotReady, check_connection_schema, verify_schema
from app.models.voting import Base
from app.main import app, lifespan, health_ready
from fastapi import HTTPException
from pathlib import Path


class ConfigurationTests(unittest.TestCase):
    def settings(self):
        with patch.dict(os.environ, {"APP_ENV": "staging", "ALLOW_MOCK_AUTH": "false",
                "DATABASE_URL": "postgresql+asyncpg://user:password@db.example.org/vote",
                "FRONTEND_ORIGIN": "https://frontend.example.org", "SESSION_SECRET": "s" * 40,
                "GOOGLE_CLIENT_ID": "client", "GOOGLE_CLIENT_SECRET": "secret",
                "GOOGLE_REDIRECT_URI": "https://backend.example.org/api/auth/google/callback",
                "ALLOWED_EMAIL_DOMAIN": "ukma.edu.ua", "ELECTION_CLOSER_ENABLED": "true",
                "SESSION_COOKIE_SAMESITE": "none"}, clear=True):
            return get_settings()

    def test_both_deployed_environments_reject_unsafe_configuration(self):
        for environment in ("staging", "production"):
            settings = replace(self.settings(), app_env=environment)
            self.assertEqual(deployment_problems(settings), [])
            for changes in (
                {"allow_mock_auth": True}, {"database_url": ""},
                {"database_url": "sqlite+aiosqlite:///local.sqlite"},
                {"database_url": "postgresql+asyncpg://u:p@localhost/vote"},
                {"frontend_origins": ("http://frontend.example.org",)},
                {"frontend_origins": ("https://frontend.example.org/path",)},
                {"frontend_origins": ("https://*.example.org",)},
                {"frontend_origins": ()}, {"session_secret": "short"},
                {"google_client_secret": " "}, {"google_client_id": ""},
                {"google_redirect_uri": "https://backend.example.org/wrong"},
                {"google_redirect_uri": "https://backend.example.org/api/auth/google/callback?code=private"},
                {"closer_enabled": False}, {"allowed_email_domain": ""},
            ):
                with self.subTest(environment=environment, fields=list(changes)):
                    self.assertTrue(deployment_problems(replace(settings, **changes)))

    def test_invalid_values_fail_without_echoing_supplied_values(self):
        for key in ("ACCESS_EXPIRES_SECONDS", "REFRESH_EXPIRES_SECONDS", "ALLOW_MOCK_AUTH", "ELECTION_CLOSER_INTERVAL_SECONDS"):
            with patch.dict(os.environ, {key: "private-value-not-to-log"}):
                with self.assertRaises(ValueError) as error:
                    get_settings()
                self.assertIn(key, str(error.exception))
                self.assertNotIn("private-value", str(error.exception))
        self.assertTrue(deployment_problems(replace(self.settings(), app_env="stagign")))

    def test_mock_defaults_off_outside_local(self):
        for environment in ("staging", "production"):
            with patch.dict(os.environ, {"APP_ENV": environment}, clear=True):
                self.assertFalse(get_settings().allow_mock_auth)


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        self.scripts = ScriptDirectory(str(Path(__file__).resolve().parents[1] / "alembic"))

    def test_empty_database_is_rejected_without_creating_any_tables(self):
        with self.engine.connect() as connection:
            with self.assertRaises(SchemaNotReady):
                check_connection_schema(connection)
            self.assertEqual(inspect(connection).get_table_names(), [])

    def test_missing_version_old_version_and_fake_stamp_are_rejected(self):
        with self.engine.begin() as connection:
            Base.metadata.create_all(connection)
            with self.assertRaises(SchemaNotReady):
                check_connection_schema(connection)
            context = MigrationContext.configure(connection)
            context.stamp(self.scripts, "8e4c2a7b9d10")
            with self.assertRaises(SchemaNotReady):
                check_connection_schema(connection)
            context.stamp(self.scripts, "head")
            check_connection_schema(connection)
            connection.execute(text("ALTER TABLE users DROP COLUMN role"))
            with self.assertRaises(SchemaNotReady):
                check_connection_schema(connection)


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_fails_closed_on_empty_database(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.addAsyncCleanup(engine.dispose)
        with patch("app.main.engine", engine), patch.dict(os.environ, {"APP_ENV": "local"}):
            with self.assertRaisesRegex(RuntimeError, "alembic"):
                async with lifespan(app):
                    self.fail("Empty database must not start")
            async with engine.connect() as connection:
                self.assertEqual(await connection.run_sync(lambda c: inspect(c).get_table_names()), [])
            with self.assertRaises(HTTPException) as error:
                await health_ready()
            self.assertEqual(error.exception.status_code, 503)

    async def test_unsafe_staging_is_rejected_before_database_access(self):
        settings = ConfigurationTests().settings()
        with patch("app.main.get_settings", return_value=replace(settings, allow_mock_auth=True)), \
                patch("app.main.verify_schema", AsyncMock()) as verify:
            with self.assertRaisesRegex(RuntimeError, "ALLOW_MOCK_AUTH"):
                async with lifespan(app):
                    self.fail("Unsafe staging must not start")
            verify.assert_not_awaited()

    async def test_connection_failure_does_not_expose_credentials(self):
        with patch("app.main.verify_schema", AsyncMock(side_effect=RuntimeError("private-db-password"))), \
                patch.dict(os.environ, {"APP_ENV": "local"}):
            with self.assertRaises(RuntimeError) as error:
                async with lifespan(app):
                    pass
            self.assertNotIn("private-db-password", str(error.exception))
            with self.assertRaises(HTTPException) as error:
                await health_ready()
            self.assertNotIn("private-db-password", error.exception.detail)

    async def test_migrated_database_starts_without_writes(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.addAsyncCleanup(engine.dispose)
        scripts = ScriptDirectory(str(Path(__file__).resolve().parents[1] / "alembic"))
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(lambda c: MigrationContext.configure(c).stamp(scripts, "head"))
        await verify_schema(engine)
        with patch("app.main.engine", engine), patch.dict(os.environ, {"APP_ENV": "local", "ELECTION_CLOSER_ENABLED": "false"}):
            async with lifespan(app):
                self.assertEqual(await health_ready(), {"status": "ready"})


class LoggingTests(unittest.TestCase):
    def test_access_log_preserves_status_but_removes_every_query_value(self):
        record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0,
            '%s - "%s %s HTTP/%s" %d',
            ("127.0.0.1", "GET", "/api/auth/google/callback?code=oauth-secret&state=state-secret", "1.1", 303), None)
        PrivacyFilter().filter(record)
        self.assertIn('/api/auth/google/callback HTTP/1.1" 303', record.getMessage())
        self.assertNotIn("oauth-secret", record.getMessage())
        self.assertNotIn("state-secret", record.getMessage())

    def test_sqlalchemy_pool_cannot_bypass_filter_via_last_resort(self):
        root = logging.getLogger()
        stream = io.StringIO()
        with patch.object(root, "handlers", []), patch("sys.stderr", stream):
            configure_private_logging()
            logging.getLogger("sqlalchemy.pool").error("private-pool-details")
        self.assertNotIn("private-pool-details", stream.getvalue())
        self.assertIn("omitted for privacy", stream.getvalue())

    def test_driver_exceptions_and_sql_payloads_do_not_reach_output(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(PrivacyFilter())
        logger = logging.Logger("sqlalchemy.engine")
        logger.addHandler(handler)
        try:
            raise ValueError("token=private-token candidate_id=private-choice")
        except ValueError:
            logger.exception("SQL with private-email and private-password")
        self.assertNotIn("private-", stream.getvalue())
        self.assertIn("ValueError", stream.getvalue())
