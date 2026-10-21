"""Exercise the email-verification migration on an isolated legacy users table."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


class EmailVerificationMigrationTests(unittest.TestCase):
    def migration(self):
        path = Path(__file__).resolve().parents[1] / "alembic/versions/b4c5d6e7f8a9_email_verification.py"
        spec = importlib.util.spec_from_file_location("email_verification_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_upgrade_adds_unverified_default_and_downgrade_removes_fields(self):
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.execute(sa.text(
                "CREATE TABLE users (id CHAR(32) PRIMARY KEY, email VARCHAR(255) NOT NULL)"
            ))
            connection.execute(sa.text(
                "INSERT INTO users (id, email) VALUES "
                "('00000000000000000000000000000001', 'user@ukma.edu.ua')"
            ))
            module = self.migration()
            with mock.patch.object(module, "op", Operations(MigrationContext.configure(connection))):
                module.upgrade()
                row = connection.execute(sa.text(
                    "SELECT id,email,email_verified,email_verified_at,email_verified_by FROM users"
                )).one()
                self.assertEqual(row[0], "00000000000000000000000000000001")
                self.assertEqual(row[1], "user@ukma.edu.ua")
                self.assertFalse(row[2])
                self.assertIsNone(row[3])
                self.assertIsNone(row[4])
                module.downgrade()
                names = {column["name"] for column in sa.inspect(connection).get_columns("users")}
                self.assertNotIn("email_verified", names)
                self.assertNotIn("email_verified_at", names)
                self.assertNotIn("email_verified_by", names)
