from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import Select

from app.models.application_event import ApplicationEventType
from app.models.event import EventReservation, FarmEvent
from app.models.farm import Farm
from app.models.reservation import ReservationStatus
from app.models.user import User
from app.schemas.event import EventReservationCreate
from app.services.application_events import record_event
from app.services.clock import marketplace_today
from app.services.events import count_reserved_spots, lock_event
from app.services.reservation_status import ReservationActor, check_status_change


class EventNotFoundError(Exception):
    pass


class EventAlreadyHappenedError(Exception):
    pass


class EventFullError(Exception):
    def __init__(self, spots_remaining: int) -> None:
        super().__init__(spots_remaining)
        self.spots_remaining = spots_remaining


def _with_details(statement: Select) -> Select:
    """Load the event, its farm and the customer together with each reservation."""
    return statement.options(
        joinedload(EventReservation.event).joinedload(FarmEvent.farm),
        joinedload(EventReservation.customer),
    )


def get_event_reservation(db: Session, reservation_id: int) -> EventReservation | None:
    statement = _with_details(select(EventReservation).where(EventReservation.id == reservation_id))
    return db.scalar(statement)


def list_event_reservations_of_customer(db: Session, customer: User) -> list[EventReservation]:
    statement = _with_details(
        select(EventReservation)
        .where(EventReservation.customer_id == customer.id)
        .order_by(EventReservation.id.desc())
    )
    return list(db.scalars(statement))


def list_event_reservations_for_farm(db: Session, farm: Farm) -> list[EventReservation]:
    statement = _with_details(
        select(EventReservation)
        .join(FarmEvent, EventReservation.event_id == FarmEvent.id)
        .where(FarmEvent.farm_id == farm.id)
        .order_by(FarmEvent.event_date, FarmEvent.start_time, EventReservation.id)
    )
    return list(db.scalars(statement))


def create_event_reservation(
    db: Session, customer: User, details: EventReservationCreate
) -> EventReservation:
    """Book places at an event without ever exceeding its capacity.

    The event row is locked before the places already taken are counted, so
    bookings for one event are processed one at a time. A second booking waits
    for the first to commit and then counts it.
    """
    event = lock_event(db, details.event_id)
    if event is None:
        raise EventNotFoundError
    if event.event_date < marketplace_today():
        raise EventAlreadyHappenedError

    spots_remaining = event.capacity - count_reserved_spots(db, event.id)
    if details.party_size > spots_remaining:
        raise EventFullError(spots_remaining)

    reservation = EventReservation(
        event_id=event.id,
        customer_id=customer.id,
        party_size=details.party_size,
        status=ReservationStatus.PENDING,
    )
    db.add(reservation)
    db.flush()
    record_event(
        db,
        ApplicationEventType.FARM_EVENT_BOOKED,
        user_id=customer.id,
        farm_id=event.farm_id,
        metadata={
            "event_reservation_id": reservation.id,
            "farm_event_id": event.id,
            "event_type": event.event_type.value,
            "party_size": details.party_size,
        },
    )
    db.commit()
    return reservation


def change_event_reservation_status(
    db: Session,
    reservation: EventReservation,
    new_status: ReservationStatus,
    actor: ReservationActor,
) -> EventReservation:
    """Move a reservation to a new status.

    Places are counted from the reservations themselves, so cancelling one
    frees its places with no further bookkeeping.
    """
    # Locked with a plain single-table SELECT: PostgreSQL cannot lock through
    # the outer joins that loading the related event and customer adds.
    # scalar() reads the row, which refreshes the copy already in the session.
    db.scalar(
        select(EventReservation)
        .where(EventReservation.id == reservation.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    check_status_change(actor, reservation.status, new_status)
    reservation.status = new_status
    db.commit()
    db.refresh(reservation)
    return reservation
