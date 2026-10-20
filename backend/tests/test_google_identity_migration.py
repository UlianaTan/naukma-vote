"""Exercise the new migration on isolated legacy user tables, without a live DB."""
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


class GoogleIdentityMigrationTests(unittest.TestCase):
    def migration(self):
        path = Path(__file__).resolve().parents[1] / 'alembic/versions/9f5d3b8c1a20_google_identity.py'
        spec = importlib.util.spec_from_file_location('google_identity_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def legacy_table(self, connection):
        connection.execute(sa.text('CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL)'))

    def test_upgrade_preserves_ids_and_downgrade(self):
        engine = sa.create_engine('sqlite://')
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            self.legacy_table(connection)
            connection.execute(sa.text("INSERT INTO users VALUES (7, ' Existing@ukma.edu.ua ')"))
            module = self.migration()
            with mock.patch.object(module, 'op', Operations(MigrationContext.configure(connection))):
                module.upgrade()
                row = connection.execute(sa.text('SELECT id,email,google_sub FROM users')).one()
                self.assertEqual(tuple(row), (7, 'existing@ukma.edu.ua', None))
                connection.execute(sa.text("UPDATE users SET google_sub='stable-sub' WHERE id=7"))
                with self.assertRaises(sa.exc.IntegrityError):
                    connection.execute(sa.text("INSERT INTO users VALUES (8, 'EXISTING@ukma.edu.ua', NULL)"))
                module.downgrade()
                self.assertEqual(connection.execute(sa.text('SELECT id,email FROM users')).one()[0], 7)
                self.assertNotIn('google_sub', [c['name'] for c in sa.inspect(connection).get_columns('users')])

    def test_ambiguous_accounts_stop_before_schema_or_data_changes(self):
        engine = sa.create_engine('sqlite://')
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            self.legacy_table(connection)
            connection.execute(sa.text("INSERT INTO users VALUES (1, 'A@ukma.edu.ua'), (2, 'a@ukma.edu.ua')"))
            module = self.migration()
            with mock.patch.object(module, 'op', Operations(MigrationContext.configure(connection))):
                with self.assertRaisesRegex(RuntimeError, 'Conflicting normalized'):
                    module.upgrade()
            self.assertEqual(connection.scalar(sa.text('SELECT count(*) FROM users')), 2)
            self.assertNotIn('google_sub', [c['name'] for c in sa.inspect(connection).get_columns('users')])

    def test_postgresql_index_matches_reflected_database_expression(self):
        # PostgreSQL rewrites trim(email) to TRIM(BOTH FROM email), which
        # Alembic treats as a changed index. Ordinary ltrim/rtrim calls round-trip.
        from app.models.voting import User
        context = MigrationContext.configure(dialect_name='postgresql')
        index = next(i for i in User.__table__.indexes if i.name == 'uq_users_email_normalized')
        reflected = sa.Index('uq_users_email_normalized', sa.text(
            'lower(ltrim(rtrim(email)))'), unique=True)
        comparison = context.impl.compare_indexes(index, reflected)
        self.assertTrue(comparison.is_equal, comparison.message)
