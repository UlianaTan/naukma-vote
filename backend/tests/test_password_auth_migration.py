"""The additive password migration preserves existing Google identities."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


class PasswordAuthMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_preserve_existing_data_and_constraints(self):
        path = Path(__file__).resolve().parents[1] / 'alembic/versions/d7e8f9a0b1c2_add_password_auth.py'
        spec = importlib.util.spec_from_file_location('password_auth_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        engine = sa.create_engine('sqlite://')
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.execute(sa.text('CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, google_sub VARCHAR(255) UNIQUE, role VARCHAR(20))'))
            connection.execute(sa.text("INSERT INTO users VALUES (7, 'existing@ukma.edu.ua', 'existing-sub', 'ADMIN')"))
            with mock.patch.object(module, 'op', Operations(MigrationContext.configure(connection))):
                module.upgrade()
                row = connection.execute(sa.text('SELECT id,email,google_sub,role,password_hash FROM users')).one()
                self.assertEqual(tuple(row), (7, 'existing@ukma.edu.ua', 'existing-sub', 'ADMIN', None))
                connection.execute(sa.text("UPDATE users SET password_hash='test-hash' WHERE id=7"))
                with self.assertRaises(sa.exc.IntegrityError):
                    connection.execute(sa.text("INSERT INTO users (id,email,google_sub) VALUES (8,'other@ukma.edu.ua','existing-sub')"))
                module.downgrade()
                self.assertEqual(tuple(connection.execute(sa.text('SELECT id,email,google_sub,role FROM users')).one()),
                                 (7, 'existing@ukma.edu.ua', 'existing-sub', 'ADMIN'))
                self.assertNotIn('password_hash', [c['name'] for c in sa.inspect(connection).get_columns('users')])
