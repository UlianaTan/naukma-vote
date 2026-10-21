"""Double-submit CSRF check for cookie-authenticated mutation requests."""
import secrets

from fastapi import HTTPException, Request

from app.core.config import get_settings


async def csrf_protect(request: Request) -> None:
    if request.method in {'GET', 'HEAD', 'OPTIONS'}:
        return
    settings = get_settings()
    cookie = request.cookies.get('csrf_token', '')
    header = request.headers.get('X-CSRF-Token', '')
    if not cookie or not header or not secrets.compare_digest(cookie.encode(), header.encode()):
        raise HTTPException(status_code=403, detail='Missing or invalid CSRF token')
    origin = request.headers.get('origin')
    if origin and origin not in settings.frontend_origins:
        raise HTTPException(status_code=403, detail='Origin not allowed')
