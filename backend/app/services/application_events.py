"""Recording what happens in the marketplace for the analytics pipeline.

Two kinds of event are recorded differently:

- An action that changes data (a reservation, a commitment, a crop request,
  a grow offer, a stock update, an event booking) is recorded in the same
  transaction as the change. The event exists if and only if the action was
  saved, so the pipeline never counts something that was rolled back.
- Browsing (searches, listings shown, farm profiles read) changes nothing. Its
  events are saved on their own and best effort: a failure is logged and the
  request is answered as if nothing had happened.
"""

import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.application_event import ApplicationEvent, ApplicationEventType
from app.models.farm import Farm
from app.schemas.common import normalize_crop_name
from app.schemas.product import ProductSearchParams, ProductSearchResult

logger = logging.getLogger(__name__)

# Searches keep the area they were made from, never the point: coordinates
# rounded to one decimal place, a cell about 7 miles across.
_REGION_GRID = Decimal("0.1")


def region_coordinate(degrees: float) -> float:
    """A coordinate snapped to the analytics region grid.

    Ties round away from zero, the same as PostgreSQL's round(), which the
    pipeline uses for farms and crop requests, so all three share one grid.
    """
    return float(Decimal(str(degrees)).quantize(_REGION_GRID, rounding=ROUND_HALF_UP))


def record_event(
    db: Session,
    event_type: ApplicationEventType,
    *,
    user_id: int | None = None,
    farm_id: int | None = None,
    product_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Add an event to the session. Does not commit.

    Call it before committing the action the event describes, so the two are
    saved or discarded together.
    """
    db.add(
        ApplicationEvent(
            event_type=event_type,
            user_id=user_id,
            farm_id=farm_id,
            product_id=product_id,
            event_metadata=metadata or {},
        )
    )


def _commit_browsing_events(db: Session, description: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not record %s", description)


def record_product_search(
    db: Session, params: ProductSearchParams, results: list[ProductSearchResult]
) -> None:
    """Record a product search and the listings it showed.

    Searches need no account, so these events carry no user. Every listing in
    the results counts as a product view and every farm shown as a farm view,
    because the result list is where customers see listings: there is no
    separate product or farm page. A shared search_id ties them together.
    """
    search_id = uuid.uuid4().hex
    search_metadata = {
        "search_id": search_id,
        # The spelling crop requests use, so searches and requests for one crop group together.
        "search_term": normalize_crop_name(params.query) if params.query else None,
        "category": params.category.value if params.category else None,
        "radius_miles": params.radius_miles,
        "available_only": params.available_only,
        "sort": params.sort.value,
        "result_count": len(results),
        "region_latitude": region_coordinate(params.latitude),
        "region_longitude": region_coordinate(params.longitude),
    }
    record_event(db, ApplicationEventType.SEARCH_PERFORMED, metadata=search_metadata)
    if not results:
        record_event(db, ApplicationEventType.NO_SEARCH_RESULT, metadata=search_metadata)

    shown_farm_ids: set[int] = set()
    for position, result in enumerate(results, start=1):
        record_event(
            db,
            ApplicationEventType.PRODUCT_VIEWED,
            farm_id=result.farm.id,
            product_id=result.product.id,
            metadata={"search_id": search_id, "position": position},
        )
        if result.farm.id not in shown_farm_ids:
            shown_farm_ids.add(result.farm.id)
            record_event(
                db,
                ApplicationEventType.FARM_VIEWED,
                farm_id=result.farm.id,
                metadata={"search_id": search_id, "source": "product_search"},
            )
    _commit_browsing_events(db, "a product search")


def record_farm_profile_view(db: Session, farm: Farm) -> None:
    """Record that a farm's public profile was read. Anonymous, like the profile itself."""
    record_event(
        db,
        ApplicationEventType.FARM_VIEWED,
        farm_id=farm.id,
        metadata={"source": "farm_profile"},
    )
    _commit_browsing_events(db, "a farm profile view")
