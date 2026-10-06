import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import DatabaseSession
from app.schemas.health import HealthStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def read_health(db: DatabaseSession) -> HealthStatus:
    # A round-trip to PostgreSQL makes this endpoint report whether the API
    # can actually serve requests, not only whether the process is running.
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check could not reach the database")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None
    return HealthStatus(status="ok")
