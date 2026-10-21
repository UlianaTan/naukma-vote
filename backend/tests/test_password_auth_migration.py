"""Exercise the Google-to-password migration on an isolated legacy schema."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


class PasswordAuthMigrationTests(unittest.TestCase):
    def migration(self):
        path = Path(__file__).resolve().parents[1] / "alembic/versions/a3b2c1d4e5f6_first_party_password_auth.py"
        spec = importlib.util.spec_from_file_location("password_auth_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_upgrade_replaces_google_sub_and_downgrade_restores_it(self):
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.execute(sa.text("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    google_sub VARCHAR(255),
                    CONSTRAINT uq_users_google_sub UNIQUE (google_sub)
                )
            """))
            connection.execute(sa.text(
                "INSERT INTO users (id, email, google_sub) VALUES (7, 'existing@ukma.edu.ua', 'old-sub')"
            ))
            module = self.migration()
            with mock.patch.object(module, "op", Operations(MigrationContext.configure(connection))):
                module.upgrade()
                columns = {column["name"] for column in sa.inspect(connection).get_columns("users")}
                self.assertIn("password_hash", columns)
                self.assertNotIn("google_sub", columns)
                self.assertEqual(
                    connection.execute(sa.text("SELECT id,email,password_hash FROM users")).one(),
                    (7, "existing@ukma.edu.ua", None),
                )
                module.downgrade()
                columns = {column["name"] for column in sa.inspect(connection).get_columns("users")}
                self.assertIn("google_sub", columns)
                self.assertNotIn("password_hash", columns)
