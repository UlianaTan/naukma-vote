"""Host-only session cookies; OAuth state keeps Lax for the Google redirect."""
import secrets

from fastapi import Response

from app.core.config import get_settings


def set_session_cookie(response: Response, name: str, value: str, lifetime: int) -> None:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    response.set_cookie(name, value, max_age=lifetime, path="/", httponly=True,
                        secure=settings.cookie_secure, samesite=settings.cookie_samesite)


def set_csrf_cookie(response: Response, token: str | None = None) -> str:
    token = token or secrets.token_urlsafe(32)
    set_session_cookie(response, "csrf_token", token, get_settings().refresh_expires_seconds)
    return token


def set_session_cookies(response: Response, access: str, refresh: str) -> None:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    set_session_cookie(response, "access_token", access, settings.access_expires_seconds)
    set_session_cookie(response, "refresh_token", refresh, settings.refresh_expires_seconds)
    set_csrf_cookie(response)


def clear_session_cookies(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    for name in ("access_token", "refresh_token", "csrf_token"):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure,
                               httponly=True, samesite=settings.cookie_samesite)
