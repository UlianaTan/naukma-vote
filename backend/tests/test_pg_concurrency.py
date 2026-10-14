"""Інтеграційні тести паралельності на справжньому PostgreSQL.

За замовчуванням ПРОПУСКАЮТЬСЯ (CI не має Postgres). Запуск:

    export TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/naukma_vote_test
    python -m unittest tests.test_pg_concurrency -v      # з каталогу backend

УВАГА: тест робить drop_all/create_all! Ім'я БД у URL має містити "test",
інакше тест відмовиться стартувати.
"""
import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.enums import ElectionStatus, UserRole
from app.models.voting import (
    Base, Ballot, Candidate, Election, EligibleVoter, User, VoterParticipation,
)
from app.services import election_service
from app.services.integrity_service import CRITICAL, validate_database
from app.services.voting_service import VotingService

URL = os.getenv("TEST_DATABASE_URL")


@unittest.skipUnless(URL, "TEST_DATABASE_URL не задано")
class PgConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if "test" not in URL.rsplit("/", 1)[-1].lower():
            self.skipTest("Ім'я тестової БД має містити 'test'")
        self.engine = create_async_engine(URL)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def seed(self, voters: int):
        now = datetime.now(timezone.utc)
        admin = User(id=uuid.uuid4(), email="admin@ukma.edu.ua", role=UserRole.ADMIN)
        election = Election(
            id=uuid.uuid4(), title="Race", status=ElectionStatus.ACTIVE, created_by=admin.id,
            starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1))
        cands = [Candidate(id=uuid.uuid4(), election_id=election.id, name=n) for n in ("A", "B")]
        users = [User(id=uuid.uuid4(), email=f"u{i}@ukma.edu.ua") for i in range(voters)]
        async with self.Session() as db:
            db.add_all([admin, election])
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