import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin_elections import router as admin_elections_router
from app.api.v1.elections import router as elections_router
from app.api.v1.auth import router as auth_router
from app.core.config import get_settings, deployment_problems
from app.core.dependencies import get_current_user
from app.database import AsyncSessionLocal, engine
from app.services.closer import run_closer_loop
from app.core.schema import SchemaNotReady, verify_schema
from app.core.logging import configure_private_logging
from app.middleware.csrf import csrf_protect

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

configure_private_logging()
logger = logging.getLogger("naukma.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    problems = deployment_problems(settings)
    if problems:
        raise RuntimeError("Небезпечна конфігурація: " + "; ".join(problems))

    # All environments use Alembic. Startup only reads the current schema.
    try:
        await asyncio.wait_for(verify_schema(engine), timeout=10)
    except SchemaNotReady as exc:
        raise RuntimeError(str(exc)) from None
    except Exception:
        raise RuntimeError("Не вдалося перевірити БД. Перевірте доступність і налаштування підключення.") from None

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

# Дозволені адреси фронтенду: FRONTEND_ORIGIN (+ localhost лише для local)
# Налаштування CORS без wildcard з credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутери
# Authenticate before CSRF so requests without a valid session return 401.
# FastAPI caches the same dependency used by endpoints and role checks.
app.include_router(admin_elections_router, dependencies=[Depends(get_current_user), Depends(csrf_protect)])
app.include_router(elections_router, prefix="/api/v1", dependencies=[Depends(get_current_user), Depends(csrf_protect)])
app.include_router(auth_router, prefix="/api/auth")


@app.get("/")
async def root():
    return {"message": "NaUKMA Vote API is running"}


@app.get("/health", tags=["Ops"])
async def health():
    """Процес живий. Без звернень до БД і без чутливих даних."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["Ops"])
async def health_ready():
    """Готовність: БД доступна й має потрібну версію схеми."""
    try:
        await asyncio.wait_for(verify_schema(engine), timeout=10)
    except Exception:  # noqa: BLE001
        logger.error("Перевірка готовності БД не пройшла")
        raise HTTPException(status_code=503, detail="Database schema unavailable or not ready")
    return {"status": "ready"}


# Prometheus metrics and middleware
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
HTTP_REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        # ensure exceptions propagate but don't break metrics collection
        raise
    latency = time.time() - start
    try:
        # Route templates bound cardinality; IDs and arbitrary 404 paths must
        # never allocate a separate Prometheus series. Normalize unknown verbs too.
        route = request.scope.get("route")
        path = getattr(route, "path", None) or "unmatched"
        method = request.method if request.method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"} else "OTHER"
        status = str(response.status_code)
        HTTP_REQUEST_LATENCY.labels(method=method, path=path).observe(latency)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
    except Exception:
        pass
    return response


@app.get("/health/live", tags=["Ops"])
async def health_live():
    """Лів-ендпоїнт — процес працює."""
    return {"status": "alive"}


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
