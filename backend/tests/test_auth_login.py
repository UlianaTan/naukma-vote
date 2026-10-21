import unittest

import httpx
from sqlalchemy import func, select

from app.models.voting import RefreshToken, User
from app.models.enums import UserRole
from app.services.passwords import hash_password, verify_password
from tests.test_qa_api import ApiTestCase, app, voter_email, voter_id, ADMIN, PUBLIC, HOUR


class PasswordTests(unittest.TestCase):
    def test_argon2_hash_and_password_length_policy(self):
        encoded = hash_password("correct-horse-battery")
        self.assertTrue(encoded.startswith("$argon2id$"))
        self.assertNotEqual(encoded, "correct-horse-battery")
        self.assertTrue(verify_password("correct-horse-battery", encoded))
        self.assertFalse(verify_password("wrong-password", encoded))
        for password in ["short", "x" * 1025]:
            with self.assertRaises(ValueError):
                hash_password(password)

    def test_unknown_account_and_invalid_hash_fail_closed(self):
        self.assertFalse(verify_password("any-password", None))
        self.assertFalse(verify_password("any-password", "invalid-encoded-hash"))


class PasswordLoginTests(ApiTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.Session() as db:
            user = await db.get(User, voter_id(1001))
            user.password_hash = hash_password("correct-horse-battery")
            await db.commit()
        self.browser = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )
        self.addAsyncCleanup(self.browser.aclose)

    async def test_login_issues_existing_session_cookies_and_user(self):
        response = await self.browser.post("/api/auth/login", json={
            "email": voter_email(1001).upper(), "password": "correct-horse-battery",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user"], {
            "id": str(voter_id(1001)),
            "email": voter_email(1001),
            "role": "voter",
        })
        self.assertIn("access_token", self.browser.cookies)
        self.assertIn("refresh_token", self.browser.cookies)
        self.assertIn("csrf_token", self.browser.cookies)
        self.assertEqual((await self.browser.get("/api/auth/me")).json()["id"], str(voter_id(1001)))
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("access_token", response.text)
        self.assertNotIn("refresh_token", response.text)

    async def test_wrong_password_and_unprovisioned_account_are_indistinguishable(self):
        bad_password = await self.browser.post("/api/auth/login", json={
            "email": voter_email(1001), "password": "wrong-password",
        })
        unknown_email = await self.browser.post("/api/auth/login", json={
            "email": "unknown@ukma.edu.ua", "password": "wrong-password",
        })
        self.assertEqual(bad_password.status_code, 401)
        self.assertEqual(unknown_email.status_code, 401)
        self.assertEqual(bad_password.json(), unknown_email.json())
        self.assertFalse(self.browser.cookies)
        async with self.Session() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(User)), 23)
            self.assertEqual(await db.scalar(select(func.count()).select_from(RefreshToken)), 0)

    async def test_login_rejects_malformed_payload(self):
        for payload in [
            {"email": "invalid", "password": "a"},
            {"email": voter_email(1001), "password": "x" * 1025},
        ]:
            response = await self.browser.post("/api/auth/login", json=payload)
            self.assertEqual(response.status_code, 422)

    async def test_register_creates_voter_hashes_password_and_issues_session(self):
        response = await self.browser.post("/api/auth/register", json={
            "email": "new-voter@ukma.edu.ua",
            "password": "correct-horse-battery",
        })
        self.assertEqual(response.status_code, 201, response.text)
        user_data = response.json()["user"]
        self.assertEqual(user_data["email"], "new-voter@ukma.edu.ua")
        self.assertEqual(user_data["role"], "voter")
        self.assertIn("access_token", self.browser.cookies)
        self.assertIn("refresh_token", self.browser.cookies)
        self.assertEqual((await self.browser.get("/api/auth/me")).json()["id"], user_data["id"])
        async with self.Session() as db:
            user = await db.scalar(select(User).where(User.email == "new-voter@ukma.edu.ua"))
            self.assertEqual(user.role, UserRole.VOTER)
            self.assertTrue(verify_password("correct-horse-battery", user.password_hash))

    async def test_register_accepts_only_ukma_domain(self):
        response = await self.browser.post("/api/auth/register", json={
            "email": "outside@example.com",
            "password": "correct-horse-battery",
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.browser.cookies)

    async def test_register_rejects_short_password_and_duplicate_email(self):
        short = await self.browser.post("/api/auth/register", json={
            "email": "new-voter@ukma.edu.ua", "password": "short",
        })
        self.assertEqual(short.status_code, 422)
        duplicate = await self.browser.post("/api/auth/register", json={
            "email": voter_email(1001), "password": "correct-horse-battery",
        })
        self.assertEqual(duplicate.status_code, 409)

    async def test_register_rejects_untrusted_origin(self):
        response = await self.browser.post(
            "/api/auth/register",
            json={"email": "new-voter@ukma.edu.ua", "password": "correct-horse-battery"},
            headers={"Origin": "https://attacker.test"},
        )
        self.assertEqual(response.status_code, 403)

    async def test_mock_login_endpoint_is_removed(self):
        response = await self.browser.post("/api/auth/mock-login")
        self.assertEqual(response.status_code, 404)

    async def test_login_rejects_untrusted_origin(self):
        response = await self.browser.post(
            "/api/auth/login",
            json={"email": voter_email(1001), "password": "correct-horse-battery"},
            headers={"Origin": "https://attacker.test"},
        )
        self.assertEqual(response.status_code, 403)


    async def test_registration_then_logout_login_and_real_vote(self):
        # A whitelist email can precede registration, and votes still use the real API.
        email = "new.participant@ukma.edu.ua"
        draft = await self.create_draft()
        eid = draft["id"]
        added = await self.client.post(f"{ADMIN}/{eid}/voters", json={"emails": [email]})
        self.assertEqual(added.status_code, 200, added.text)
        self.assertEqual((await self.lifecycle(eid, "activate")).status_code, 200)
        await self.set_window(eid, -HOUR, HOUR)
        payload = {"email": email.upper(), "password": "correct-horse-battery"}
        registered = await self.browser.post("/api/auth/register", json={**payload, "role": "admin"})
        self.assertEqual(registered.status_code, 201, registered.text)
        user = registered.json()["user"]
        self.assertEqual(user["role"], "voter")
        csrf = self.browser.cookies.get("csrf_token")
        logout = await self.browser.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
        self.assertEqual(logout.status_code, 200, logout.text)
        self.assertEqual((await self.browser.get("/api/auth/me")).status_code, 401)
        logged_in = await self.browser.post("/api/auth/login", json=payload)
        self.assertEqual(logged_in.status_code, 200, logged_in.text)
        self.assertEqual(logged_in.json()["user"]["id"], user["id"])
        # Missing CSRF is still rejected after password login.
        vote_url = f"{PUBLIC}/{eid}/vote"
        choice = {"candidate_id": draft["candidates"][0]["id"]}
        self.assertEqual((await self.browser.post(vote_url, json=choice)).status_code, 403)
        headers = {"X-CSRF-Token": self.browser.cookies.get("csrf_token")}
        self.assertEqual((await self.browser.post(vote_url, json=choice, headers=headers)).status_code, 200)
        self.assertEqual((await self.browser.post(vote_url, json=choice, headers=headers)).status_code, 409)
        self.assertEqual(await self.db_counts(eid), (1, 1))
        self.browser.cookies.delete("access_token")
        refreshed = await self.browser.post("/api/auth/refresh", headers=headers)
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual((await self.browser.get("/api/auth/me")).json()["id"], user["id"])

    async def test_google_account_cannot_be_overwritten_by_registration(self):
        async with self.Session() as db:
            user = await db.get(User, voter_id(1002))
            user.google_sub = "existing-google-sub"
            await db.commit()
        response = await self.browser.post("/api/auth/register", json={
            "email": voter_email(1002).upper(), "password": "attacker-password-123"})
        self.assertEqual(response.status_code, 409)
        login = await self.browser.post("/api/auth/login", json={
            "email": voter_email(1002), "password": "attacker-password-123"})
        self.assertEqual(login.status_code, 401)
        async with self.Session() as db:
            user = await db.get(User, voter_id(1002))
            self.assertEqual(user.google_sub, "existing-google-sub")
            self.assertIsNone(user.password_hash)

    async def test_registration_normalization_domain_and_validation_privacy(self):
        password = "private-short"
        for email in ["person@sub.ukma.edu.ua", "person@ukma.edu.ua.example.org"]:
            response = await self.browser.post("/api/auth/register", json={
                "email": email, "password": "correct-horse-battery"})
            self.assertEqual(response.status_code, 400)
        response = await self.browser.post("/api/auth/register", json={
            "email": "  Normalized@UKMA.EDU.UA  ", "password": "correct-horse-battery"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["email"], "normalized@ukma.edu.ua")
        duplicate = await self.browser.post("/api/auth/register", json={
            "email": "NORMALIZED@ukma.edu.ua", "password": "correct-horse-battery"})
        self.assertEqual(duplicate.status_code, 409)
        for path in ["/api/auth/register", "/api/auth/login"]:
            response = await self.browser.post(path, json={"email": "invalid", "password": password})
            self.assertEqual(response.status_code, 422)
            self.assertNotIn(password, response.text)
            self.assertNotIn('"input"', response.text)

    async def test_registration_integrity_race_returns_conflict_without_session(self):
        from unittest import mock
        from sqlalchemy.exc import IntegrityError
        from sqlalchemy.ext.asyncio import AsyncSession
        with mock.patch.object(AsyncSession, "commit", side_effect=IntegrityError("insert", {}, Exception("collision"))):
            response = await self.browser.post("/api/auth/register", json={
                "email": "racing@ukma.edu.ua", "password": "correct-horse-battery"})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertFalse(self.browser.cookies)

    async def test_staging_password_sessions_keep_secure_cookie_policy(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {
            "APP_ENV": "staging", "SESSION_COOKIE_SAMESITE": "none",
            "FRONTEND_ORIGIN": "https://frontend.test",
        }):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="https://backend.test") as browser:
                response = await browser.post("/api/auth/register", json={
                    "email": "secure-cookie-qa@ukma.edu.ua", "password": "correct-horse-battery"},
                    headers={"Origin": "https://frontend.test"})
                self.assertEqual(response.status_code, 201, response.text)
                for cookie in response.headers.get_list("set-cookie"):
                    self.assertIn("HttpOnly", cookie)
                    self.assertIn("Secure", cookie)
                    self.assertIn("SameSite=none", cookie)
                self.assertNotIn("correct-horse-battery", response.text)
                self.assertNotIn("password_hash", response.text)
                self.assertEqual((await browser.get("/api/auth/me")).status_code, 200)
