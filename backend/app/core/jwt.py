"""Short-lived, signed access tokens; refresh tokens use separate opaque secrets."""
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings

ISSUER = 'naukma-vote'
AUDIENCE = 'naukma-vote-api'


def _secret() -> str:
    secret = get_settings().session_secret
    if len(secret.encode()) < 32:
        raise RuntimeError('SESSION_SECRET must contain at least 32 bytes')
    return secret


def create_access_token(user_id: str) -> str:
    subject = str(uuid.UUID(user_id))
    lifetime = get_settings().access_expires_seconds
    if lifetime <= 0:
        raise ValueError('ACCESS_EXPIRES_SECONDS must be positive')
    now = datetime.now(timezone.utc)
    return jwt.encode({
        'sub': subject, 'iat': now, 'exp': now + timedelta(seconds=lifetime),
        'iss': ISSUER, 'aud': AUDIENCE, 'type': 'access', 'jti': str(uuid.uuid4()),
    }, _secret(), algorithm='HS256')


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, _secret(), algorithms=['HS256'], audience=AUDIENCE,
                         issuer=ISSUER, options={'require': ['sub', 'iat', 'exp', 'type', 'jti']})
    if payload['type'] != 'access':
        raise jwt.InvalidTokenError('Incorrect token type')
    try:
        uuid.UUID(payload['sub'])
    except (ValueError, TypeError, AttributeError) as exc:
        raise jwt.InvalidTokenError('Invalid subject') from exc
    return payload
