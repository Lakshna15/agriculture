from fastapi import FastAPI

from app.errors import register_error_handlers
from app.log_redaction import redact_query_strings_in_access_log
from app.middleware.body_size_limit import BodySizeLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
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

redact_query_strings_in_access_log()

app = FastAPI(title="Farm2Local API", version="0.1.0")

register_error_handlers(app)
# Middleware added last runs first. Security headers wrap everything, so even
# the size limit's 413 carries them, and the size limit runs before any
# request body reaches the application.
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

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
