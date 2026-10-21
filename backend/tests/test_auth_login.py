import unittest

import httpx
from sqlalchemy import func, select

from app.models.voting import RefreshToken, User
from app.models.enums import UserRole
from app.services.passwords import hash_password, verify_password
from tests.test_qa_api import ApiTestCase, app, voter_email, voter_id


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

    async def test_operator_provisioning_stores_hash_and_preserves_existing_role(self):
        from app.cli.provision_user import provision_user

        email = "operator-created@ukma.edu.ua"
        first_hash = hash_password("first-password-123")
        async with self.Session() as db:
            self.assertTrue(await provision_user(db, email, first_hash, None))
            user = await db.scalar(select(User).where(User.email == email))
            self.assertEqual(user.role, UserRole.VOTER)
            self.assertEqual(user.password_hash, first_hash)
            self.assertNotEqual(user.password_hash, "first-password-123")
            user.role = UserRole.ADMIN
            await db.commit()

        next_hash = hash_password("another-password-123")
        async with self.Session() as db:
            self.assertFalse(await provision_user(db, email, next_hash, None))
            user = await db.scalar(select(User).where(User.email == email))
            self.assertEqual(user.role, UserRole.ADMIN)
            self.assertEqual(user.password_hash, next_hash)
