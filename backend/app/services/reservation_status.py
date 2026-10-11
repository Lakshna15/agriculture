"""Who may move a reservation from one status to another.

The rules are the same for product reservations and event reservations:

    PENDING ──farm confirms──▶ CONFIRMED ──farm completes──▶ COMPLETED
       │                           │
       └────── either side cancels ┴──────▶ CANCELLED

COMPLETED and CANCELLED are final.
"""

import enum

from app.models.reservation import ReservationStatus

PENDING = ReservationStatus.PENDING
CONFIRMED = ReservationStatus.CONFIRMED
COMPLETED = ReservationStatus.COMPLETED
CANCELLED = ReservationStatus.CANCELLED


class ReservationActor(enum.Enum):
    """The side of a reservation a user is acting for."""

    CUSTOMER = "customer"
    FARMER = "farmer"


_ALLOWED_TRANSITIONS: dict[ReservationActor, dict[ReservationStatus, set[ReservationStatus]]] = {
    ReservationActor.FARMER: {
        PENDING: {CONFIRMED, CANCELLED},
        CONFIRMED: {COMPLETED, CANCELLED},
    },
    ReservationActor.CUSTOMER: {
        PENDING: {CANCELLED},
        CONFIRMED: {CANCELLED},
    },
}


class StatusChangeNotPermittedError(Exception):
    """The actor is never allowed to set this status, whatever the current one is."""


class InvalidStatusTransitionError(Exception):
    """The actor may set this status, but not from the reservation's current status."""

    def __init__(self, current_status: ReservationStatus, new_status: ReservationStatus) -> None:
        super().__init__(f"{current_status} -> {new_status}")
        self.current_status = current_status
        self.new_status = new_status


def check_status_change(
    actor: ReservationActor, current_status: ReservationStatus, new_status: ReservationStatus
) -> None:
    transitions = _ALLOWED_TRANSITIONS[actor]
    statuses_the_actor_can_set = set().union(*transitions.values())
    if new_status not in statuses_the_actor_can_set:
        raise StatusChangeNotPermittedError(new_status)
    if new_status not in transitions.get(current_status, set()):
        raise InvalidStatusTransitionError(current_status, new_status)
