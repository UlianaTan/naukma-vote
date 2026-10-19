import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.admin_elections import router as admin_elections_router
from app.api.v1.elections import router as elections_router
from app.api.v1.auth import router as auth_router
from app.core.config import get_settings, production_problems
from app.database import AsyncSessionLocal, engine
from app.services.closer import run_closer_loop
from app.models.voting import Base as ModelsBase

logger = logging.getLogger("naukma.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # У production небезпечна конфігурація = відмова стартувати (fail fast)
    problems = production_problems(settings)
    if problems:
        raise RuntimeError(
            "Небезпечна production-конфігурація: " + "; ".join(problems)
        )

    # Для локальної розробки переконаємось, що таблиці створені (без alembic).
    # У production / CI рекомендується використовувати alembic.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(ModelsBase.metadata.create_all)
    except Exception:
        logger.exception("Error while creating metadata tables")

    stop_event = asyncio.Event()
    closer_task = None
    if settings.closer_enabled:
        closer_task = asyncio.create_task(
            run_closer_loop(AsyncSessionLocal, settings.closer_interval_seconds, stop_event)
        )
    try:
        yield
    finally:
        stop_event.set()
        if closer_task:
            await closer_task


app = FastAPI(
    title="NaUKMA Vote API",
    version="1.0.0",
    description="Elections & Voting Core API with guaranteed voter anonymity",
    lifespan=lifespan,
)

# Дозволені адреси фронтенду: FRONTEND_ORIGIN (+ localhost поза production)
# Налаштування CORS без wildcard з credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутери
app.include_router(admin_elections_router)
app.include_router(elections_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/auth")


@app.get("/")
async def root():
    return {"message": "NaUKMA Vote API is running"}


@app.get("/health", tags=["Ops"])
async def health():
    """Процес живий. Без звернень до БД і без чутливих даних."""
    return {"status": "ok"}


@app.get("/health/live", tags=["Ops"])
async def health_live():
    """Лів-ендпоїнт — процес працює.
    Використовується для перевірки життєздатності контейнера/процесу."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Ops"])
async def health_ready():
    """Готовність: БД відповідає. Деталі помилки не розкриваються."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        logger.exception("Перевірка готовності: БД недоступна")
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready"}

# Метрики та middleware додаються в окремому модулі під час наступних комітів
