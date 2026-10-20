"""Конфігурація середовища (змінні оточення) та перевірка production-налаштувань."""
import os
from dataclasses import dataclass
from pathlib import Path

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
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


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
    origins = frontend if app_env == "production" else tuple(dict.fromkeys(frontend + LOCAL_ORIGINS))
    return Settings(
        app_env=app_env,
        frontend_origins=origins,
        # Mock-авторизація (X-User-Id) за замовчуванням вимкнена в production.
        allow_mock_auth=_env_bool("ALLOW_MOCK_AUTH", app_env != "production"),
        closer_enabled=_env_bool("ELECTION_CLOSER_ENABLED", True),
        closer_interval_seconds=max(1.0, _env_float("ELECTION_CLOSER_INTERVAL_SECONDS", 5.0)),
        allowed_email_domain=os.getenv("ALLOWED_EMAIL_DOMAIN", "ukma.edu.ua").strip().lstrip("@").lower(),
        database_url=os.getenv("DATABASE_URL", ""),
        session_secret=os.getenv("SESSION_SECRET", ""),
        access_expires_seconds=int(os.getenv("ACCESS_EXPIRES_SECONDS", "900")),
        refresh_expires_seconds=int(os.getenv("REFRESH_EXPIRES_SECONDS", "2592000")),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", ""),
    )


def production_problems(settings: Settings) -> list[str]:
    """Критичні проблеми конфігурації; у production застосунок з ними не стартує."""
    if not settings.is_production:
        return []
    problems: list[str] = []
    if settings.allow_mock_auth:
        problems.append("ALLOW_MOCK_AUTH=true заборонено в production (mock X-User-Id)")
    if not settings.database_url:
        problems.append("DATABASE_URL не задано")
    elif DEFAULT_LOCAL_DATABASE_MARKER in settings.database_url or "@localhost" in settings.database_url:
        problems.append("DATABASE_URL вказує на локальну БД/дефолтні облікові дані")
    if not settings.frontend_origins:
        problems.append("FRONTEND_ORIGIN не задано (потрібен для CORS)")
    for origin in settings.frontend_origins:
        if not origin.startswith("https://"):
            problems.append(f"FRONTEND_ORIGIN має бути https: {origin}")
    if not settings.closer_enabled:
        problems.append("ELECTION_CLOSER_ENABLED=false: таймер закриття вимкнено")
    if len(settings.session_secret.encode()) < 32:
        problems.append("SESSION_SECRET має містити щонайменше 32 байти")
    # GOOGLE keys are optional; if frontend expects google auth in production, these must be set
    if settings.google_client_id == "" or settings.google_client_secret == "":
        problems.append("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET не задані")
    if settings.google_redirect_uri == "":
        problems.append("GOOGLE_REDIRECT_URI не задано")
    return problems
