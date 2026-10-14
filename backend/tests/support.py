"""Спільні хелпери для тестів з SQLite (синхронна сесія під async-інтерфейсом)."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models.enums import ElectionStatus, UserRole
from app.models.voting import Base, Candidate, Election, EligibleVoter, User


class AsyncAdapter:
    """Мінімальний async-фасад над sync Session для сервісного коду."""

    def __init__(self, session):
        self.session = session

    def add(self, obj):
        self.session.add(obj)

    def add_all(self, objs):
        self.session.add_all(objs)

    async def execute(self, query):
        return self.session.execute(query)

    async def scalar(self, query):
        return self.session.scalar(query)

    async def get(self, model, ident):
        return self.session.get(model, ident)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    async def refresh(self, obj):
        self.session.refresh(obj)

    async def delete(self, obj):
        self.session.delete(obj)


class AdapterContext:
    """Імітує `async with session_factory() as db` для коду таймера."""

    def __init__(self, db):
        self.db = db

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *exc):
        return False


def make_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine, Session(engine, expire_on_commit=False)


def now_utc():
    return datetime.now(timezone.utc)


def make_user(session, email="student@ukma.edu.ua", role=UserRole.VOTER):
    user = User(id=uuid.uuid4(), email=email, role=role)
    session.add(user)
    session.commit()
    return user


def make_election(
    session,
    admin,
    *,
    status=ElectionStatus.ACTIVE,
    starts_delta=timedelta(hours=-1),
    ends_delta=timedelta(hours=1),
    candidates=("Анна", "Борис"),
    voters=("student@ukma.edu.ua",),
):
    now = now_utc()
    election = Election(
        id=uuid.uuid4(), title="Тестові вибори", status=status, created_by=admin.id,
        starts_at=now + starts_delta, ends_at=now + ends_delta,
    )
    session.add(election)
    session.flush()
    cands = [Candidate(id=uuid.uuid4(), election_id=election.id, name=n) for n in candidates]
    session.add_all(cands)
    session.add_all([EligibleVoter(election_id=election.id, email=e) for e in voters])
    session.commit()
    return election, cands