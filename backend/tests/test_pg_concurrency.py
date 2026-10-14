"""Інтеграційні тести паралельності на справжньому PostgreSQL.

Локально пропускаються без TEST_DATABASE_URL. CI запускає їх на окремій PostgreSQL 16.
Запуск:

    export TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/naukma_vote_test
    python -m unittest discover -s tests -p test_pg_concurrency.py -v      # з каталогу backend

Кожен тест використовує власну випадкову PostgreSQL-схему. Наявні таблиці
не видаляються. Назва БД має закінчуватися на _test або _ci.
"""
import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.enums import ElectionStatus, UserRole
from app.models.voting import (
    Base, Ballot, Candidate, Election, EligibleVoter, User, VoterParticipation,
)
from app.services import election_service
from app.services.integrity_service import CRITICAL, validate_database
from app.services.voting_service import VotingService

URL = os.getenv("TEST_DATABASE_URL")


def validate_test_database_url(url: str) -> None:
    database = make_url(url).database or ""
    if not database.lower().endswith(("_test", "_ci")):
        raise ValueError("Назва тестової БД має закінчуватися на _test або _ci")


@unittest.skipUnless(URL, "TEST_DATABASE_URL не задано")
class PgConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        validate_test_database_url(URL)
        self.schema = "voting_test_" + uuid.uuid4().hex
        self.admin_engine = create_async_engine(URL)
        async with self.admin_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_async_engine(
            URL, connect_args={"server_settings": {"search_path": self.schema}}
        )
        self.addAsyncCleanup(self.cleanup_schema)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)

    async def cleanup_schema(self):
        await self.engine.dispose()
        async with self.admin_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        await self.admin_engine.dispose()

    async def seed(self, voters: int):
        now = datetime.now(timezone.utc)
        admin = User(id=uuid.uuid4(), email="admin@ukma.edu.ua", role=UserRole.ADMIN)
        election = Election(
            id=uuid.uuid4(), title="Race", status=ElectionStatus.ACTIVE, created_by=admin.id,
            starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1))
        cands = [Candidate(id=uuid.uuid4(), election_id=election.id, name=n) for n in ("A", "B")]
        users = [User(id=uuid.uuid4(), email=f"u{i}@ukma.edu.ua") for i in range(voters)]
        async with self.Session() as db:
            db.add(admin)
            await db.flush()
            db.add(election)
            await db.flush()
            db.add_all(cands + users)
            db.add_all([EligibleVoter(election_id=election.id, email=u.email) for u in users])
            await db.commit()
        return election, cands, users

    async def vote(self, election, cand, user):
        async with self.Session() as db:
            try:
                await VotingService.cast_vote(db, election.id, cand.id, user)
                return 200
            except HTTPException as exc:
                return exc.status_code

    async def counts(self, election_id):
        async with self.Session() as db:
            ballots = await db.scalar(select(func.count(Ballot.id)).where(Ballot.election_id == election_id))
            parts = await db.scalar(
                select(func.count(VoterParticipation.id)).where(VoterParticipation.election_id == election_id))
        return ballots, parts

    async def test_parallel_votes_from_distinct_users_all_counted(self):
        election, cands, users = await self.seed(25)
        codes = await asyncio.gather(*[self.vote(election, cands[i % 2], u) for i, u in enumerate(users)])
        self.assertEqual(set(codes), {200})
        self.assertEqual(await self.counts(election.id), (25, 25))

    async def test_same_user_parallel_votes_count_once(self):
        election, cands, users = await self.seed(1)
        codes = await asyncio.gather(*[self.vote(election, cands[i % 2], users[0]) for i in range(10)])
        self.assertEqual(codes.count(200), 1)
        self.assertEqual(codes.count(409), 9)
        self.assertEqual(await self.counts(election.id), (1, 1))

    async def test_turnout_stays_consistent_while_votes_commit(self):
        election, cands, users = await self.seed(25)

        async def read_turnout():
            for _ in range(30):
                async with self.Session() as db:
                    out = await VotingService.get_turnout(db, election.id)
                    self.assertTrue(out.consistent)

        await asyncio.gather(
            read_turnout(),
            *[self.vote(election, cands[i % 2], user) for i, user in enumerate(users)],
        )
        self.assertEqual(await self.counts(election.id), (25, 25))

    async def test_votes_racing_with_close_stay_consistent(self):
        election, cands, users = await self.seed(40)

        async def close_later():
            await asyncio.sleep(0.02)
            async with self.Session() as db:
                await election_service.close_election(db, election.id, None, "timer")

        results = await asyncio.gather(
            *[self.vote(election, cands[i % 2], u) for i, u in enumerate(users)], close_later())
        codes = results[:-1]
        self.assertTrue(set(codes) <= {200, 400}, set(codes))  # жодних 500/409
        ballots, parts = await self.counts(election.id)
        # Усі прийняті голоси враховані, жоден голос після закриття не пройшов
        self.assertEqual((ballots, parts), (codes.count(200), codes.count(200)))
        async with self.Session() as db:
            self.assertEqual((await db.get(Election, election.id)).status, ElectionStatus.CLOSED)
            issues = await validate_database(db, election.id)
        self.assertFalse([i for i in issues if i.severity == CRITICAL])
        # Підрахунок після закриття не змінюється
        await asyncio.sleep(0.05)
        self.assertEqual(await self.counts(election.id), (ballots, parts))


if __name__ == "__main__":
    unittest.main()
