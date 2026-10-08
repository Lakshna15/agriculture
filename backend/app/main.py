from fastapi import FastAPI

from app.routers import auth, farms, health

app = FastAPI(title="Farm2Local API", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router, prefix="/api")
app.include_router(farms.router, prefix="/api")
