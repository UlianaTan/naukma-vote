"""Real PostgreSQL races; each test runs in its own disposable schema."""
import asyncio
import unittest

from sqlalchemy import func, select

from tests import test_qa_api as qa
from app.models.voting import User
from app.services.google_oauth import OAuthFailure, resolve_google_user


@unittest.skipUnless(qa.PG_URL, 'TEST_DATABASE_URL не задано')
class GoogleOAuthConcurrencyTests(qa.ApiTestCase):
    async def race(self, subjects, email):
        barrier = asyncio.Barrier(len(subjects))

        async def login(subject):
            async with self.Session() as db:
                # Start all identity lookups together on separate DB connections.
                await barrier.wait()
                try:
                    user = await resolve_google_user(db, subject, email, link_legacy=True)
                    return user.id
                except OAuthFailure as exc:
                    await db.rollback()
                    return exc.code

        return await asyncio.wait_for(asyncio.gather(*(login(s) for s in subjects)), timeout=30)

    async def test_parallel_first_login_has_one_user(self):
        ids = await self.race(['same-sub'] * 6, 'parallel-new@ukma.edu.ua')
        self.assertEqual(len(set(ids)), 1)
        self.assertNotIn('account_conflict', ids)
        async with self.Session() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(User).where(
                User.google_sub == 'same-sub')), 1)

    async def test_parallel_legacy_link_keeps_original_id(self):
        ids = await self.race(['legacy-sub'] * 6, qa.voter_email(1001))
        self.assertEqual(set(ids), {qa.voter_id(1001)})

    async def test_competing_subjects_cannot_claim_same_account(self):
        results = await self.race(['subject-a', 'subject-b'], qa.voter_email(1001))
        self.assertEqual(results.count(qa.voter_id(1001)), 1)
        self.assertEqual(results.count('account_conflict'), 1)
