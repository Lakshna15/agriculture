from fastapi import HTTPException, status

from app.models.farm import Farm
from app.models.reservation import ReservationStatus
from app.models.user import User, UserRole
from app.services.reservation_status import InvalidStatusTransitionError, ReservationActor


def resolve_reservation_actor(user: User, customer_id: int, farm: Farm) -> ReservationActor:
    """Decide which side of a reservation the user is on, or refuse access.

    Only the customer who made the reservation and the farmer who owns the
    farm it concerns may act on it. Everyone else, including other customers
    and other farmers, is rejected.
    """
    if user.role is UserRole.CUSTOMER and user.id == customer_id:
        return ReservationActor.CUSTOMER
    if user.role is UserRole.FARMER and user.id == farm.owner_id:
        return ReservationActor.FARMER
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this reservation",
    )


def status_change_not_permitted(new_status: ReservationStatus) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You are not allowed to mark a reservation as {new_status.value}",
    )


def invalid_status_transition(error: InvalidStatusTransitionError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"A {error.current_status.value} reservation cannot be changed "
            f"to {error.new_status.value}"
        ),
    )
