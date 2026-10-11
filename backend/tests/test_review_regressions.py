import unittest
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.v1.admin_elections import create_election_draft, update_election_draft
from app.core.dependencies import ADMIN_USER_ID, get_current_user
from app.models.voting import Base, Election, ElectionStatus
from app.schemas.admin_elections import ElectionCreate, ElectionUpdate
from app.services.voting_service import is_duplicate_vote_error

class AsyncAdapter:
    def __init__(self, session): self.session = session
    def add(self, obj): self.session.add(obj)
    async def execute(self, query): return self.session.execute(query)
    async def flush(self): self.session.flush()
    async def commit(self): self.session.commit()
    async def refresh(self, obj): self.session.refresh(obj)

class DraftTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        @event.listens_for(self.engine, 'connect')
        def enable_fk(connection, _): connection.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.db = AsyncAdapter(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    async def test_create_draft_on_empty_database_uses_persisted_admin(self):
        admin = await get_current_user(db=self.db)
        now = datetime.now(timezone.utc)
        election = await create_election_draft(ElectionCreate(
            title='Test election', starts_at=now+timedelta(days=1),
            ends_at=now+timedelta(days=2)), self.db, admin)
        self.assertEqual(election.created_by, ADMIN_USER_ID)
        self.assertEqual(self.session.get(Election, election.id).created_by, admin.id)

    async def test_partial_date_patch_cannot_invert_interval(self):
        admin = await get_current_user(db=self.db)
        now = datetime.now(timezone.utc)
        election = Election(id=uuid.uuid4(), title='Test election',
            status=ElectionStatus.DRAFT, created_by=admin.id,
            starts_at=now+timedelta(days=1), ends_at=now+timedelta(days=2))
        self.session.add(election)
        self.session.commit()
        with self.assertRaises(HTTPException) as caught:
            await update_election_draft(election.id, ElectionUpdate(ends_at=now), self.db, admin)
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(election.ends_at, now+timedelta(days=2))

class ValidationTests(unittest.TestCase):
    def test_timezone_less_input_is_validation_error(self):
        with self.assertRaises(ValidationError):
            ElectionCreate(title='Test election', starts_at='2030-01-01T10:00:00', ends_at='2030-01-02T10:00:00')

    def test_required_fields_reject_explicit_null(self):
        for field in ['title', 'starts_at', 'ends_at']:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ElectionUpdate(**{field: None})

    def test_only_participation_unique_constraint_means_duplicate(self):
        for state, name, expected in [('23505', 'uq_user_election_vote', True),
                ('23503', 'voter_participations_user_id_fkey', False),
                ('23505', 'users_email_key', False)]:
            with self.subTest(state=state, name=name):
                driver = Exception('driver failure')
                driver.sqlstate = state
                driver.constraint_name = name
                wrapper = Exception('wrapped driver failure')
                wrapper.__cause__ = driver
                error = IntegrityError('INSERT INTO voter_participations ...', {}, wrapper)
                self.assertEqual(is_duplicate_vote_error(error), expected)
