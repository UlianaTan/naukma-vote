from fastapi import FastAPI
from app.api.v1.admin_elections import router as admin_elections_router
from app.api.v1.elections import router as elections_router

app = FastAPI(
    title="NaUKMA Vote API",
    version="1.0.0",
    description="Elections & Voting Core API with guaranteed voter anonymity",
)

# Роутер адміністратора (Тиждень 4)
app.include_router(admin_elections_router)

# Роутер публічних виборів та прийому голосів (Тиждень 5)
app.include_router(elections_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "NaUKMA Vote API is running"}