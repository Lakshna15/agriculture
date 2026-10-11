import pytest

from app.models.reservation import ReservationStatus
from app.services.reservation_status import (
    InvalidStatusTransitionError,
    ReservationActor,
    StatusChangeNotPermittedError,
    check_status_change,
)

PENDING = ReservationStatus.PENDING
CONFIRMED = ReservationStatus.CONFIRMED
COMPLETED = ReservationStatus.COMPLETED
CANCELLED = ReservationStatus.CANCELLED
FARMER = ReservationActor.FARMER
CUSTOMER = ReservationActor.CUSTOMER


@pytest.mark.parametrize(
    ("actor", "current_status", "new_status"),
    [
        (FARMER, PENDING, CONFIRMED),
        (FARMER, PENDING, CANCELLED),
        (FARMER, CONFIRMED, COMPLETED),
        (FARMER, CONFIRMED, CANCELLED),
        (CUSTOMER, PENDING, CANCELLED),
        (CUSTOMER, CONFIRMED, CANCELLED),
    ],
)
def test_allowed_status_changes(
    actor: ReservationActor, current_status: ReservationStatus, new_status: ReservationStatus
) -> None:
    check_status_change(actor, current_status, new_status)


@pytest.mark.parametrize(
    ("actor", "current_status", "new_status"),
    [
        (FARMER, PENDING, COMPLETED),
        (FARMER, CONFIRMED, CONFIRMED),
        (FARMER, COMPLETED, CANCELLED),
        (FARMER, COMPLETED, CONFIRMED),
        (FARMER, CANCELLED, CONFIRMED),
        (FARMER, CANCELLED, CANCELLED),
        (CUSTOMER, COMPLETED, CANCELLED),
        (CUSTOMER, CANCELLED, CANCELLED),
    ],
)
def test_status_changes_that_are_invalid_from_the_current_status(
    actor: ReservationActor, current_status: ReservationStatus, new_status: ReservationStatus
) -> None:
    with pytest.raises(InvalidStatusTransitionError):
        check_status_change(actor, current_status, new_status)


@pytest.mark.parametrize(
    ("actor", "new_status"),
    [(CUSTOMER, CONFIRMED), (CUSTOMER, COMPLETED), (CUSTOMER, PENDING), (FARMER, PENDING)],
)
@pytest.mark.parametrize("current_status", list(ReservationStatus))
def test_statuses_an_actor_may_never_set(
    actor: ReservationActor, current_status: ReservationStatus, new_status: ReservationStatus
) -> None:
    with pytest.raises(StatusChangeNotPermittedError):
        check_status_change(actor, current_status, new_status)
