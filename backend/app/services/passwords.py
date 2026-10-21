"""Argon2id password hashing and verification."""
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 1024


def hash_password(password: str) -> str:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters")
    return _hasher.hash(password)


def verify_password(password: str, encoded_hash: str | None) -> bool:
    """Verify credentials with a dummy hash for unknown/unprovisioned accounts."""
    stored_hash = encoded_hash or _DUMMY_HASH
    try:
        matches = _hasher.verify(stored_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False
    return bool(encoded_hash and matches)
