from fastapi import FastAPI

from app.routers import auth, event_reservations, events, farms, health, products, reservations

app = FastAPI(title="Farm2Local API", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router, prefix="/api")
app.include_router(farms.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(reservations.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(event_reservations.router, prefix="/api")
