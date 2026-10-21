"""Конфігурація середовища та перевірки staging/production перед запуском."""
import math
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

LOCAL_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
)
DEFAULT_LOCAL_DATABASE_MARKER = "postgres:postgres@"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
        raise ValueError(f"{name}: очікується true або false")
    return value in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        if not math.isfinite(value) or value <= 0:
            raise ValueError
        return value
    except ValueError:
        raise ValueError(f"{name}: очікується додатне число") from None


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
        if value <= 0:
            raise ValueError
        return value
    except ValueError:
        raise ValueError(f"{name}: очікується додатне ціле число") from None


@dataclass(frozen=True)
class Settings:
    app_env: str
    frontend_origins: tuple[str, ...]
    allow_mock_auth: bool
    closer_enabled: bool
    closer_interval_seconds: float
    allowed_email_domain: str
    database_url: str
    session_secret: str
    access_expires_seconds: int
    refresh_expires_seconds: int
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    @property
    def cookie_secure(self) -> bool:
        return self.app_env != "local"

    @property
    def cookie_samesite(self) -> str:
        value = os.getenv("SESSION_COOKIE_SAMESITE", "lax" if self.app_env == "local" else "none").lower()
        if value not in {"lax", "strict", "none"}:
            raise ValueError("SESSION_COOKIE_SAMESITE must be lax, strict or none")
        if value == "none" and not self.cookie_secure:
            raise ValueError("SameSite=None requires HTTPS (Secure cookies)")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def get_settings() -> Settings:
    """Читає змінні при кожному виклику (дешево; зручно для тестів)."""
    app_env = os.getenv("APP_ENV", "local").strip().lower()
    frontend = tuple(
        o.strip().rstrip("/")
        for o in os.getenv("FRONTEND_ORIGIN", "").split(",")
        if o.strip()
    )
    origins = tuple(dict.fromkeys(frontend + LOCAL_ORIGINS)) if app_env == "local" else frontend
    return Settings(
        app_env=app_env,
        frontend_origins=origins,
        # Mock-авторизація (X-User-Id) за замовчуванням дозволена лише локально.
        allow_mock_auth=_env_bool("ALLOW_MOCK_AUTH", app_env == "local"),
        closer_enabled=_env_bool("ELECTION_CLOSER_ENABLED", True),
        closer_interval_seconds=max(1.0, _env_float("ELECTION_CLOSER_INTERVAL_SECONDS", 5.0)),
        allowed_email_domain=os.getenv("ALLOWED_EMAIL_DOMAIN", "ukma.edu.ua").strip().lstrip("@").lower(),
        database_url=os.getenv("DATABASE_URL", ""),
        session_secret=os.getenv("SESSION_SECRET", ""),
        access_expires_seconds=_env_int("ACCESS_EXPIRES_SECONDS", 900),
        refresh_expires_seconds=_env_int("REFRESH_EXPIRES_SECONDS", 2592000),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", ""),
    )


def _https_url(value: str, *, origin: bool = False) -> bool:
    if any(ord(character) <= 32 for character in value):
        return False
    try:
        parsed = urlsplit(value)
        _ = parsed.port
        return bool(
            parsed.scheme == "https" and parsed.hostname
            and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment
            and (not origin or parsed.path == "")
        )
    except ValueError:
        return False


def deployment_problems(settings: Settings) -> list[str]:
    """Fail closed for unknown environments; staging and production share safeguards."""
    if settings.app_env not in {"local", "staging", "production"}:
        return ["APP_ENV має бути local, staging або production"]
    if settings.app_env == "local":
        return []
    problems: list[str] = []
    if settings.allow_mock_auth:
        problems.append("ALLOW_MOCK_AUTH=true заборонено поза local")
    try:
        database = make_url(settings.database_url)
        if (database.drivername != "postgresql+asyncpg" or not database.database
                or not database.host or database.host.lower() in {"localhost", "127.0.0.1", "::1"}
                or DEFAULT_LOCAL_DATABASE_MARKER in settings.database_url):
            problems.append("DATABASE_URL має вказувати на окрему PostgreSQL через asyncpg")
    except Exception:
        problems.append("DATABASE_URL не задано або має некоректний формат")
    if not settings.frontend_origins or any(not _https_url(o, origin=True) for o in settings.frontend_origins):
        problems.append("FRONTEND_ORIGIN має містити точні HTTPS origin без шляху, query або wildcard")
    if any("*" in origin for origin in settings.frontend_origins):
        problems.append("Wildcard у FRONTEND_ORIGIN заборонено")
    if not settings.closer_enabled:
        problems.append("ELECTION_CLOSER_ENABLED=false: таймер закриття вимкнено")
    if len(settings.session_secret.encode()) < 32 or not settings.session_secret.strip():
        problems.append("SESSION_SECRET має містити щонайменше 32 байти")
    if not settings.google_client_id.strip() or not settings.google_client_secret.strip():
        problems.append("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET не задані")
    if (not _https_url(settings.google_redirect_uri)
            or urlsplit(settings.google_redirect_uri).path != "/api/auth/google/callback"):
        problems.append("GOOGLE_REDIRECT_URI має бути точним HTTPS callback /api/auth/google/callback")
    if not settings.allowed_email_domain:
        problems.append("ALLOWED_EMAIL_DOMAIN не може бути порожнім для університетського входу")
    try:
        _ = settings.cookie_samesite
    except ValueError:
        problems.append("SESSION_COOKIE_SAMESITE має бути lax, strict або none")
    return problems


def production_problems(settings: Settings) -> list[str]:
    """Compatibility alias for existing callers; includes staging safeguards."""
    return deployment_problems(settings)
