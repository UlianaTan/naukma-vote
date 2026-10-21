"""Ensure the obsolete administrator verification fields can be removed/restored."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


class RemoveEmailVerificationMigrationTests(unittest.TestCase):
    def test_upgrade_removes_fields_and_downgrade_restores_them(self):
        path = Path(__file__).resolve().parents[1] / (
            "alembic/versions/c6d7e8f9a0b1_remove_email_verification.py"
        )
        spec = importlib.util.spec_from_file_location("remove_email_verification_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)

        with engine.begin() as connection:
            connection.execute(sa.text(
                "CREATE TABLE users (id CHAR(32) PRIMARY KEY, email VARCHAR(255) NOT NULL, "
                "email_verified BOOLEAN NOT NULL DEFAULT 0, email_verified_at DATETIME, "
                "email_verified_by CHAR(32), CONSTRAINT fk_users_email_verified_by_users "
                "FOREIGN KEY(email_verified_by) REFERENCES users(id) ON DELETE SET NULL)"
            ))
            with mock.patch.object(module, "op", Operations(MigrationContext.configure(connection))):
                module.upgrade()
                names = {column["name"] for column in sa.inspect(connection).get_columns("users")}
                self.assertNotIn("email_verified", names)
                self.assertNotIn("email_verified_at", names)
                self.assertNotIn("email_verified_by", names)
                module.downgrade()
                names = {column["name"] for column in sa.inspect(connection).get_columns("users")}
                self.assertIn("email_verified", names)
                self.assertIn("email_verified_at", names)
                self.assertIn("email_verified_by", names)
