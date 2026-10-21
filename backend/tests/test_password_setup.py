"""First-password setup preserves the current Google identity."""
import uuid
from unittest import mock

import httpx
from sqlalchemy import update

from tests.test_qa_api import ApiTestCase, app, voter_id, voter_email, session_headers
from app.models.voting import User, Election
from app.services.passwords import hash_password, verify_password

PASSWORD = 'local-setup-test-password'


class PasswordSetupTests(ApiTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.user_id = voter_id(1001)
        async with self.Session() as db:
            user = await db.get(User, self.user_id)
            user.google_sub = 'google-setup-sub'
            await db.commit()
        self.browser = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',
                                         headers=session_headers(self.user_id))
        self.addAsyncCleanup(self.browser.aclose)

    async def test_setup_once_preserves_account_and_enables_password_login(self):
        draft = await self.create_draft()
        before = (await self.browser.get('/api/auth/me')).json()
        self.assertTrue(before['needs_password_setup'])
        response = await self.browser.post('/api/auth/password', json={'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['user'], {**before, 'needs_password_setup': False})
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertNotIn('password_hash', response.text)
        self.assertNotIn(PASSWORD, response.text)
        self.assertFalse((await self.browser.get('/api/auth/me')).json()['needs_password_setup'])
        async with self.Session() as db:
            user = await db.get(User, self.user_id)
            original_hash = user.password_hash
            self.assertTrue(verify_password(PASSWORD, original_hash))
            self.assertEqual(user.google_sub, 'google-setup-sub')
            self.assertEqual((await db.get(Election, uuid.UUID(draft['id']))).created_by,
                             uuid.UUID(draft['created_by']))
        repeat = await self.browser.post('/api/auth/password', json={'password': 'a-different-password'})
        self.assertEqual(repeat.status_code, 409)
        async with self.Session() as db:
            self.assertEqual((await db.get(User, self.user_id)).password_hash, original_hash)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as fresh:
            login = await fresh.post('/api/auth/login', json={'email': voter_email(1001), 'password': PASSWORD})
            self.assertEqual(login.status_code, 200, login.text)
            self.assertEqual(login.json()['user']['id'], str(self.user_id))
            self.assertFalse(login.json()['user']['needs_password_setup'])

    async def test_unauthenticated_csrf_and_origin_rejected_without_changes(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as anon:
            self.assertEqual((await anon.post('/api/auth/password', json={'password': PASSWORD})).status_code, 401)
        headers = session_headers(self.user_id)
        headers['X-CSRF-Token'] = ''
        self.assertEqual((await self.client.post('/api/auth/password', headers=headers,
                                                json={'password': PASSWORD})).status_code, 403)
        self.assertEqual((await self.browser.post('/api/auth/password', headers={'Origin': 'https://attacker.test'},
                                                 json={'password': PASSWORD})).status_code, 403)
        async with self.Session() as db:
            self.assertIsNone((await db.get(User, self.user_id)).password_hash)

    async def test_validation_is_private_and_cannot_target_another_user(self):
        for payload in [{'password': 'short'}, {'password': 'x' * 1025},
                        {'password': PASSWORD, 'email': voter_email(1002)},
                        {'password': PASSWORD, 'user_id': str(voter_id(1002))}]:
            response = await self.browser.post('/api/auth/password', json=payload)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertNotIn('\"' + payload['password'] + '\"', response.text)
            self.assertNotIn('"input"', response.text)
        async with self.Session() as db:
            for identity in [self.user_id, voter_id(1002)]:
                self.assertIsNone((await db.get(User, identity)).password_hash)

    async def test_non_google_user_cannot_use_setup(self):
        headers = session_headers(voter_id(1002))
        response = await self.client.post('/api/auth/password', headers=headers, json={'password': PASSWORD})
        self.assertEqual(response.status_code, 403)
        self.assertFalse((await self.client.get('/api/auth/me', headers=headers)).json()['needs_password_setup'])

    async def test_competing_setup_cannot_overwrite_first_saved_password(self):
        winning_hash = hash_password('another-tab-first-password')

        async def competing_setup(function, password):
            encoded = function(password)
            # The request loaded its user before a different tab won the update.
            async with self.Session() as db:
                await db.execute(update(User).where(User.id == self.user_id).values(password_hash=winning_hash))
                await db.commit()
            return encoded

        with mock.patch('app.api.v1.auth.run_in_threadpool', side_effect=competing_setup):
            response = await self.browser.post('/api/auth/password', json={'password': PASSWORD})
        self.assertEqual(response.status_code, 409, response.text)
        async with self.Session() as db:
            self.assertEqual((await db.get(User, self.user_id)).password_hash, winning_hash)
