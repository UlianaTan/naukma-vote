"""OAuth checks against disposable DBs, without real Google credentials."""
import os
from contextlib import contextmanager
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from tests.test_qa_api import ApiTestCase, app, voter_email, voter_id
from app.models.voting import User, RefreshToken
from app.services.google_oauth import resolve_google_user


class GoogleOAuthTests(ApiTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        patch = mock.patch.dict(os.environ, {
            'APP_ENV': 'staging', 'FRONTEND_ORIGIN': 'https://frontend.test',
            'GOOGLE_CLIENT_ID': 'test-client', 'GOOGLE_CLIENT_SECRET': 'test-secret',
            'GOOGLE_REDIRECT_URI': 'https://backend.test/api/auth/google/callback',
            'SESSION_COOKIE_SAMESITE': 'none', 'ALLOWED_EMAIL_DOMAIN': 'ukma.edu.ua',
        })
        patch.start()
        self.addCleanup(patch.stop)
        self.browser = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://backend.test')
        self.addAsyncCleanup(self.browser.aclose)

    async def begin(self, target=None):
        response = await self.browser.get('/api/auth/google/login', params={'next': target} if target else {})
        self.assertEqual(response.status_code, 303, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        params = parse_qs(urlsplit(response.headers['location']).query)
        self.assertNotIn('hd', params)
        return params['state'][0]

    @contextmanager
    def google(self, profile=None, token=None, post_error=None, get_error=None):
        client = mock.MagicMock()
        client.post = mock.AsyncMock(return_value=token if token is not None else httpx.Response(
            200, json={'access_token': 'test-token'}), side_effect=post_error)
        client.get = mock.AsyncMock(return_value=httpx.Response(200, json=profile if profile is not None else {
            'sub': 'google-sub-1001', 'email': voter_email(1001), 'email_verified': True, 'hd': 'ukma.edu.ua',
        }), side_effect=get_error)
        context = mock.MagicMock()
        context.__aenter__ = mock.AsyncMock(return_value=client)
        context.__aexit__ = mock.AsyncMock(return_value=False)
        with mock.patch('app.api.v1.auth.httpx.AsyncClient', return_value=context):
            yield client

    async def callback(self, state, **params):
        return await self.browser.get('/api/auth/google/callback', params={'state': state, 'code': 'code', **params})

    def assert_error(self, response, code):
        self.assertEqual(response.status_code, 303, response.text)
        parsed = urlsplit(response.headers['location'])
        self.assertEqual(f'{parsed.scheme}://{parsed.netloc}{parsed.path}', 'https://frontend.test/login')
        self.assertEqual(parse_qs(parsed.query), {'error': [code]})
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(response.headers['referrer-policy'], 'no-referrer')
        for cookie in ('oauth_state', 'oauth_next', 'access_token'):
            self.assertIsNone(self.browser.cookies.get(cookie))

    async def test_denial_and_provider_errors(self):
        for error, expected in [('access_denied', 'access_denied'), ('server_error', 'oauth_failed')]:
            state = await self.begin()
            with self.google() as client:
                response = await self.browser.get('/api/auth/google/callback', params={
                    'state': state, 'error': error, 'error_description': 'private-details'})
            client.post.assert_not_awaited()
            self.assert_error(response, expected)
            self.assertNotIn('private-details', response.text + str(response.headers))

    async def test_state_and_code_required(self):
        for kind, expected in [('missing', 'invalid_state'), ('wrong', 'invalid_state'),
                               ('missing_cookie', 'invalid_state'), ('missing_code', 'oauth_failed')]:
            state = await self.begin()
            params = {'code': 'code', 'state': state}
            if kind == 'missing':
                params.pop('state')
            elif kind == 'wrong':
                params['state'] = 'wrong'
            elif kind == 'missing_cookie':
                self.browser.cookies.delete('oauth_state')
            else:
                params.pop('code')
            with self.google() as client:
                response = await self.browser.get('/api/auth/google/callback', params=params)
            client.post.assert_not_awaited()
            self.assert_error(response, expected)

    async def test_consumed_callback_rejected(self):
        state = await self.begin()
        with self.google():
            await self.callback(state)
        self.browser.cookies.delete('access_token')
        with self.google() as client:
            self.assert_error(await self.callback(state), 'invalid_state')
        client.post.assert_not_awaited()

    async def test_incomplete_configuration(self):
        for env in [{'GOOGLE_CLIENT_SECRET': ''}, {'GOOGLE_CLIENT_ID': ''},
                    {'GOOGLE_REDIRECT_URI': ''}, {'SESSION_SECRET': 'short'},
                    {'GOOGLE_REDIRECT_URI': 'http://backend.test/api/auth/google/callback'},
                    {'SESSION_COOKIE_SAMESITE': 'invalid'}]:
            with mock.patch.dict(os.environ, env):
                self.assert_error(await self.browser.get('/api/auth/google/login'), 'auth_unavailable')
        with mock.patch.dict(os.environ, {'FRONTEND_ORIGIN': ''}):
            self.assertEqual((await self.browser.get('/api/auth/google/login')).status_code, 503)

    async def test_network_and_token_failures(self):
        cases = [({'post_error': httpx.ConnectError('private-details')}, 'google_unavailable'),
                 ({'get_error': httpx.ReadTimeout('private-details')}, 'google_unavailable'),
                 ({'token': httpx.Response(503)}, 'google_unavailable'),
                 ({'token': httpx.Response(400)}, 'oauth_failed'),
                 ({'token': httpx.Response(200, text='bad-json')}, 'oauth_failed'),
                 ({'token': httpx.Response(200, json=[])}, 'oauth_failed'),
                 ({'token': httpx.Response(200, json={'access_token': 123})}, 'oauth_failed')]
        for kwargs, expected in cases:
            state = await self.begin()
            with self.google(**kwargs):
                response = await self.callback(state)
            self.assert_error(response, expected)
            self.assertNotIn('private-details', response.text + str(response.headers))

    async def test_profile_validation_and_bad_userinfo(self):
        valid = {'sub': 'valid-sub', 'email': voter_email(1001), 'email_verified': True, 'hd': 'ukma.edu.ua'}
        cases = [({'email_verified': False}, 'unverified_email'),
                 ({'email_verified': 'true'}, 'unverified_email'),
                 ({'email': 'not-an-email'}, 'invalid_profile'),
                 ({'email': 'voter@gmail.com'}, 'invalid_domain'),
                 ({'email': 'voter@ukma.edu.ua.example.com'}, 'invalid_domain'),
                 ({'email': 'voter@sub.ukma.edu.ua'}, 'invalid_domain'),
                 ({'sub': ''}, 'invalid_profile'), ({'sub': 123}, 'invalid_profile')]
        for changes, expected in cases:
            state = await self.begin()
            with self.google(profile={**valid, **changes}):
                self.assert_error(await self.callback(state), expected)
        for response, expected in [(httpx.Response(200, text='bad-json'), 'oauth_failed'),
                                   (httpx.Response(503), 'google_unavailable'),
                                   (httpx.Response(401), 'oauth_failed')]:
            state = await self.begin()
            with self.google() as client:
                client.get.return_value = response
                self.assert_error(await self.callback(state), expected)
        async with self.Session() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(RefreshToken)), 0)

    async def test_legacy_link_and_repeat_login_preserve_id(self):
        async with self.Session() as db:
            user = await db.get(User, voter_id(1001))
            user.email = '  ' + voter_email(1001).upper() + '  '
            await db.commit()
        for _ in range(2):
            state = await self.begin('https://frontend.test/admin')
            with self.google():
                response = await self.callback(state)
            self.assertEqual(response.headers['location'], 'https://frontend.test/admin')
            self.assertEqual((await self.browser.get('/api/auth/me')).json()['id'], str(voter_id(1001)))
        async with self.Session() as db:
            user = await db.get(User, voter_id(1001))
            self.assertEqual(user.google_sub, 'google-sub-1001')
            self.assertEqual(user.email, voter_email(1001))

    async def test_changed_email_and_identity_conflicts(self):
        async with self.Session() as db:
            user = await db.get(User, voter_id(1001))
            user.google_sub = 'known-sub'
            await db.commit()
        profile = {'sub': 'known-sub', 'email': 'renamed@ukma.edu.ua', 'hd': 'ukma.edu.ua', 'email_verified': True}
        state = await self.begin()
        with self.google(profile=profile):
            await self.callback(state)
        self.assertEqual((await self.browser.get('/api/auth/me')).json()['id'], str(voter_id(1001)))
        self.browser.cookies.clear()
        for changes in [{'email': voter_email(1002)}, {'sub': 'different-sub'}]:
            state = await self.begin()
            with self.google(profile={**profile, **changes}):
                self.assert_error(await self.callback(state), 'account_conflict')

    async def test_new_user_is_normalized_and_not_duplicated(self):
        profile = {'sub': 'new-sub', 'email': ' New.Student@ukma.edu.ua ', 'email_verified': True}
        ids = []
        for _ in range(2):
            state = await self.begin()
            with self.google(profile=profile):
                await self.callback(state)
            me = (await self.browser.get('/api/auth/me')).json()
            self.assertEqual(me['email'], 'new.student@ukma.edu.ua')
            ids.append(me['id'])
        self.assertEqual(ids[0], ids[1])

    async def test_redirects_cannot_escape_frontend(self):
        for target in ['https://attacker.test', '//attacker.test', 'https://frontend.test.attacker.test/',
                       'https://frontend.test\\@attacker.test/', 'https://attacker.test@frontend.test/', 'https://[broken']:
            state = await self.begin(target)
            self.browser.cookies.set('oauth_next', target, domain='backend.test', path='/')
            with self.google():
                response = await self.callback(state)
            self.assertEqual(response.headers['location'], 'https://frontend.test')
            self.browser.cookies.clear()

    async def test_unique_race_retries(self):
        async with self.Session() as db:
            commit = db.commit
            calls = 0

            async def competing_commit():
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise IntegrityError('insert', {}, Exception('unique collision'))
                await commit()

            with mock.patch.object(db, 'commit', side_effect=competing_commit):
                user = await resolve_google_user(db, 'race-sub', 'race@ukma.edu.ua')
            self.assertEqual(user.google_sub, 'race-sub')
            self.assertEqual(calls, 2)

    async def test_mock_auth_defaults_off_on_staging(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('ALLOW_MOCK_AUTH', None)
            self.assertEqual((await self.browser.post('/api/auth/login')).status_code, 403)

    async def test_untrusted_third_party_email_cannot_claim_legacy_account(self):
        # An unrestricted deployment still must not trust historical ownership
        # of a third-party email just because Google reports email_verified.
        async with self.Session() as db:
            db.add(User(email='external@example.org'))
            await db.commit()
        state = await self.begin()
        profile = {'sub': 'external-sub', 'email': 'external@example.org', 'email_verified': True}
        with mock.patch.dict(os.environ, {'ALLOWED_EMAIL_DOMAIN': ''}), self.google(profile=profile):
            self.assert_error(await self.callback(state), 'account_conflict')

    async def test_completed_parallel_link_is_reused(self):
        async with self.Session() as db:
            user = await db.get(User, voter_id(1001))
            user.google_sub = 'already-linked'
            await db.commit()
            # Simulate a callback that initially saw no sub before another
            # callback finished linking, then sees the linked email record.
            with mock.patch.object(db, 'scalar', return_value=None):
                found = await resolve_google_user(db, 'already-linked', voter_email(1001), link_legacy=True)
            self.assertEqual(found.id, voter_id(1001))

    async def test_database_failure_returns_safe_error(self):
        from sqlalchemy.exc import OperationalError
        state = await self.begin()
        with self.google(), mock.patch('app.api.v1.auth.resolve_google_user', side_effect=OperationalError(
            'private-query', {}, Exception('private-database-error'))):
            response = await self.callback(state)
        self.assert_error(response, 'auth_unavailable')
        self.assertNotIn('private-', response.text + str(response.headers))
