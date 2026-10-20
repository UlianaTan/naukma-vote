import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.jwt import create_access_token, decode_access_token
from app.middleware.csrf import csrf_protect
from app.models.voting import Base, RefreshToken, User
from app.services.auth_service import create_refresh_token, verify_refresh_token, revoke_refresh_token


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'SESSION_SECRET': 'test-secret-' * 4})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_signature_expiry_and_subject(self):
        uid = str(uuid.uuid4())
        token = create_access_token(uid)
        claims = decode_access_token(token)
        self.assertEqual(claims['sub'], uid)
        with self.assertRaises(jwt.InvalidTokenError):
            decode_access_token(token + 'broken')
        claims['exp'] = datetime.now(timezone.utc) - timedelta(seconds=1)
        expired = jwt.encode(claims, os.environ['SESSION_SECRET'], algorithm='HS256')
        with self.assertRaises(jwt.ExpiredSignatureError):
            decode_access_token(expired)
        claims['exp'] = datetime.now(timezone.utc) + timedelta(minutes=1)
        claims['type'] = 'refresh'
        with self.assertRaises(jwt.InvalidTokenError):
            decode_access_token(jwt.encode(claims, os.environ['SESSION_SECRET'], algorithm='HS256'))

    def test_missing_secret_fails_closed(self):
        with patch.dict(os.environ, {'SESSION_SECRET': ''}):
            with self.assertRaises(RuntimeError):
                create_access_token(str(uuid.uuid4()))


class RefreshTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        self.addAsyncCleanup(self.engine.dispose)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def test_storage_expiry_and_revocation(self):
        async with self.Session() as db:
            user = User(email='refresh@ukma.edu.ua')
            db.add(user)
            await db.commit()
            token = await create_refresh_token(db, str(user.id))
            row = await verify_refresh_token(db, token)
            self.assertEqual(row.user_id, user.id)
            self.assertNotEqual(row.token_hash, token)
            self.assertIsNone(await verify_refresh_token(db, 'unknown'))
            await revoke_refresh_token(db, token)
            self.assertIsNone(await verify_refresh_token(db, token))
            await revoke_refresh_token(db, token)
            token2 = await create_refresh_token(db, str(user.id))
            row2 = await db.scalar(select(RefreshToken).where(RefreshToken.revoked_at.is_(None)))
            row2.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()
            self.assertIsNone(await verify_refresh_token(db, token2))


class CsrfTests(unittest.IsolatedAsyncioTestCase):
    async def test_cookie_session_requires_matching_header(self):
        def request(method='POST', cookie='csrf_token=abc; access_token=session', header=''):
            return Request({'type': 'http', 'method': method, 'headers': [
                (b'cookie', cookie.encode()), (b'x-csrf-token', header.encode()),
            ]})
        with patch.dict(os.environ, {'ALLOW_MOCK_AUTH': 'false'}):
            await csrf_protect(request('GET'))
            await csrf_protect(request(header='abc'))
            for header in ['', 'wrong']:
                with self.assertRaises(HTTPException) as caught:
                    await csrf_protect(request(header=header))
                self.assertEqual(caught.exception.status_code, 403)
        with patch.dict(os.environ, {'ALLOW_MOCK_AUTH': 'true'}):
            await csrf_protect(request(cookie=''))
            with self.assertRaises(HTTPException):
                await csrf_protect(request())
