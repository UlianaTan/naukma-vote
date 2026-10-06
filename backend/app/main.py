from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin_elections import router as admin_elections_router
from app.api.v1.elections import router as elections_router

app = FastAPI(
    title="NaUKMA Vote API",
    version="1.0.0",
    description="Elections & Voting Core API with guaranteed voter anonymity",
)

# Погоджені адреси локального фронтенду
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Налаштування CORS без wildcard з credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутер адміністратора (Тиждень 4)
app.include_router(admin_elections_router)

# Роутер публічних виборів та прийому голосів (Тиждень 5)
app.include_router(elections_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "NaUKMA Vote API is running"}