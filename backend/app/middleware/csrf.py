"""Double-submit CSRF check for cookie-authenticated mutation requests."""
import secrets

from fastapi import HTTPException, Request

from app.core.config import get_settings


async def csrf_protect(request: Request) -> None:
    if request.method in {'GET', 'HEAD', 'OPTIONS'}:
        return
    # Keep the explicitly enabled development mock API usable without a session.
    if get_settings().allow_mock_auth and not (
        request.cookies.get('access_token') or request.cookies.get('refresh_token')
    ):
        return
    cookie = request.cookies.get('csrf_token', '')
    header = request.headers.get('X-CSRF-Token', '')
    if not cookie or not header or not secrets.compare_digest(cookie.encode(), header.encode()):
        raise HTTPException(status_code=403, detail='Missing or invalid CSRF token')
    origin = request.headers.get('origin')
    if origin and origin not in get_settings().frontend_origins:
        raise HTTPException(status_code=403, detail='Origin not allowed')


async def logout_csrf_protect(request: Request) -> None:
    """Allow logout from an explicitly trusted browser origin even after expiry.

    Without Origin, require the normal CSRF pair. Never allow an untrusted Origin,
    including a request carrying an otherwise valid CSRF pair.
    """
    origin = request.headers.get('origin')
    if origin:
        if origin not in get_settings().frontend_origins:
            raise HTTPException(status_code=403, detail='Origin not allowed')
        return
    await csrf_protect(request)
