from sqlalchemy import Subquery, func, select
from sqlalchemy.orm import Session

from app.models.event import EventReservation, FarmEvent
from app.models.farm import Farm
from app.models.reservation import ReservationStatus
from app.schemas.event import (
    EventSearchFarm,
    EventSearchParams,
    EventSearchResult,
    FarmEventCreate,
    FarmEventRead,
)
from app.services.clock import marketplace_today
from app.services.geo import geography_point, meters_to_miles, miles_to_meters


class EventDateInPastError(Exception):
    pass


def _reserved_spots_by_event() -> Subquery:
    """Total party size per event, counting every reservation that is not cancelled."""
    return (
        select(
            EventReservation.event_id,
            func.sum(EventReservation.party_size).label("reserved_spots"),
        )
        .where(EventReservation.status != ReservationStatus.CANCELLED)
        .group_by(EventReservation.event_id)
        .subquery()
    )


def count_reserved_spots(db: Session, event_id: int) -> int:
    statement = select(func.coalesce(func.sum(EventReservation.party_size), 0)).where(
        EventReservation.event_id == event_id,
        EventReservation.status != ReservationStatus.CANCELLED,
    )
    return db.scalar(statement) or 0


def lock_event(db: Session, event_id: int) -> FarmEvent | None:
    """Load an event and hold a row lock on it until the transaction ends."""
    statement = (
        select(FarmEvent)
        .where(FarmEvent.id == event_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalar(statement)


def create_event(db: Session, farm: Farm, details: FarmEventCreate) -> FarmEvent:
    if details.event_date < marketplace_today():
        raise EventDateInPastError
    # FarmEventCreate has no farm_id, so the farm always comes from the session.
    event = FarmEvent(farm_id=farm.id, **details.model_dump())
    db.add(event)
    db.commit()
    return event


def list_events_of_farm(db: Session, farm: Farm) -> list[FarmEventRead]:
    """Every event of a farm, past and upcoming, soonest first."""
    reserved = _reserved_spots_by_event()
    statement = (
        select(FarmEvent, func.coalesce(reserved.c.reserved_spots, 0))
        .outerjoin(reserved, reserved.c.event_id == FarmEvent.id)
        .where(FarmEvent.farm_id == farm.id)
        .order_by(FarmEvent.event_date, FarmEvent.start_time, FarmEvent.id)
    )
    return [
        FarmEventRead.from_event(event, reserved_spots)
        for event, reserved_spots in db.execute(statement)
    ]


def search_events(db: Session, params: EventSearchParams) -> list[EventSearchResult]:
    """Find events from today onward on farms within a radius of a point, soonest first.

    Distance is evaluated by PostGIS in the same way as the product search.
    """
    search_point = geography_point(params.latitude, params.longitude)
    distance_meters = func.ST_Distance(Farm.location, search_point)
    reserved = _reserved_spots_by_event()

    statement = (
        select(
            FarmEvent,
            Farm,
            func.coalesce(reserved.c.reserved_spots, 0),
            distance_meters.label("distance_meters"),
        )
        .join(Farm, FarmEvent.farm_id == Farm.id)
        .outerjoin(reserved, reserved.c.event_id == FarmEvent.id)
        .where(FarmEvent.event_date >= marketplace_today())
        .where(func.ST_DWithin(Farm.location, search_point, miles_to_meters(params.radius_miles)))
    )
    if params.event_type is not None:
        statement = statement.where(FarmEvent.event_type == params.event_type)
    statement = statement.order_by(
        FarmEvent.event_date, FarmEvent.start_time, distance_meters.asc(), FarmEvent.id
    ).limit(params.limit)

    return [
        EventSearchResult(
            event=FarmEventRead.from_event(event, reserved_spots),
            farm=EventSearchFarm.model_validate(farm),
            distance_miles=meters_to_miles(row_distance_meters),
        )
        for event, farm, reserved_spots, row_distance_meters in db.execute(statement)
    ]
