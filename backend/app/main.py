from fastapi import FastAPI
from app.api.v1.admin_elections import router as admin_elections_router

app = FastAPI(
    title="NaUKMA Vote API",
    version="1.0.0",
)

app.include_router(admin_elections_router)

@app.get("/")
async def root():
    return {"message": "NaUKMA Vote API is running"}