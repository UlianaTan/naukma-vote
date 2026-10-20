"""Logout must clear cookies after expiry without allowing cross-site logout."""
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import update

from tests import test_qa_api as qa
from app.models.voting import RefreshToken


class LogoutSessionTests(qa.ApiTestCase):
    browser_login = qa.BrowserSessionTests.browser_login

    async def test_trusted_origin_logout_after_refresh_expiry(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=qa.app), base_url='http://test') as browser:
            await self.browser_login(browser)
            async with self.Session() as db:
                await db.execute(update(RefreshToken).values(expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)))
                await db.commit()
            self.assertEqual((await browser.get('/api/auth/me')).status_code, 200)
            self.assertEqual((await browser.get('/api/auth/csrf')).status_code, 401)
            response = await browser.post('/api/auth/logout', headers={'Origin': 'http://localhost:5173'})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(any(browser.cookies.get(k) for k in ('access_token', 'refresh_token', 'csrf_token')))
            self.assertEqual((await browser.get('/api/auth/me')).status_code, 401)

    async def test_logout_rejects_untrusted_null_and_missing_origin_without_csrf(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=qa.app), base_url='http://test') as browser:
            await self.browser_login(browser)
            token = browser.cookies.get('csrf_token')
            for headers in [{}, {'Origin': 'null'}, {'Origin': 'https://attacker.test'},
                            {'Origin': 'https://attacker.test', 'X-CSRF-Token': token}]:
                self.assertEqual((await browser.post('/api/auth/logout', headers=headers)).status_code, 403)
                self.assertEqual((await browser.get('/api/auth/me')).status_code, 200)
            self.assertEqual((await browser.post('/api/auth/logout', headers={'X-CSRF-Token': token})).status_code, 200)

    async def test_trusted_origin_logout_also_clears_invalid_cookies(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=qa.app), base_url='http://test') as browser:
            browser.cookies.set('access_token', 'expired')
            browser.cookies.set('refresh_token', 'invalid')
            response = await browser.post('/api/auth/logout', headers={'Origin': 'http://localhost:5173'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.headers.get_list('set-cookie')), 3)
