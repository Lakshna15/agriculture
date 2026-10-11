from fastapi import APIRouter, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentCustomer, CurrentFarmer, CurrentUser
from app.dependencies.path_params import ResourceId
from app.dependencies.reservations import (
    invalid_status_transition,
    resolve_reservation_actor,
    status_change_not_permitted,
)
from app.schemas.event import EventReservationCreate, EventReservationRead
from app.schemas.reservation import ReservationStatusUpdate
from app.services.event_reservations import (
    EventAlreadyHappenedError,
    EventFullError,
    EventNotFoundError,
    change_event_reservation_status,
    create_event_reservation,
    get_event_reservation,
    list_event_reservations_for_farm,
    list_event_reservations_of_customer,
)
from app.services.farms import get_farm_owned_by
from app.services.reservation_status import (
    InvalidStatusTransitionError,
    StatusChangeNotPermittedError,
)

router = APIRouter(prefix="/event-reservations", tags=["event reservations"])


@router.post("", response_model=EventReservationRead, status_code=status.HTTP_201_CREATED)
def reserve_event(
    details: EventReservationCreate, customer: CurrentCustomer, db: DatabaseSession
) -> EventReservationRead:
    try:
        reservation = create_event_reservation(db, customer, details)
    except EventNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found") from None
    except EventAlreadyHappenedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This event has already taken place",
        ) from None
    except EventFullError as error:
        detail = (
            "This event is fully booked"
            if error.spots_remaining <= 0
            else f"Only {error.spots_remaining} spots remaining"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from None
    return EventReservationRead.from_reservation(reservation)


@router.get("/mine", response_model=list[EventReservationRead])
def list_my_event_reservations(
    customer: CurrentCustomer, db: DatabaseSession
) -> list[EventReservationRead]:
    return [
        EventReservationRead.from_reservation(reservation)
        for reservation in list_event_reservations_of_customer(db, customer)
    ]


@router.get("/farm", response_model=list[EventReservationRead])
def list_event_reservations_for_my_farm(
    farmer: CurrentFarmer, db: DatabaseSession
) -> list[EventReservationRead]:
    farm = get_farm_owned_by(db, farmer)
    if farm is None:
        return []
    return [
        EventReservationRead.from_reservation(reservation)
        for reservation in list_event_reservations_for_farm(db, farm)
    ]


@router.patch("/{reservation_id}/status", response_model=EventReservationRead)
def update_event_reservation_status(
    reservation_id: ResourceId,
    update: ReservationStatusUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> EventReservationRead:
    reservation = get_event_reservation(db, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    actor = resolve_reservation_actor(current_user, reservation.customer_id, reservation.event.farm)
    try:
        reservation = change_event_reservation_status(db, reservation, update.status, actor)
    except StatusChangeNotPermittedError:
        raise status_change_not_permitted(update.status) from None
    except InvalidStatusTransitionError as error:
        raise invalid_status_transition(error) from None
    return EventReservationRead.from_reservation(reservation)
