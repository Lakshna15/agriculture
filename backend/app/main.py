from fastapi import FastAPI

from app.routers import (
    auth,
    crop_commitments,
    crop_polls,
    crop_requests,
    crop_votes,
    demand,
    event_reservations,
    events,
    farms,
    grow_offers,
    health,
    notifications,
    products,
    reservations,
)

app = FastAPI(title="Farm2Local API", version="0.1.0")

app.include_router(health.router)

api_routers = (
    auth.router,
    farms.router,
    products.router,
    reservations.router,
    events.router,
    event_reservations.router,
    crop_requests.router,
    demand.router,
    grow_offers.router,
    crop_commitments.router,
    crop_polls.router,
    crop_votes.router,
    notifications.router,
)
for api_router in api_routers:
    app.include_router(api_router, prefix="/api")
