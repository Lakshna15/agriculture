from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.models.event import EventReservation, FarmEvent, FarmEventType
from app.models.reservation import ReservationStatus
from app.schemas.common import DatabaseId, NearbySearchParams, PriceOrFree, blank_to_none
from app.schemas.reservation import ReservationFarm

MAX_EVENT_CAPACITY = 10_000


class FarmEventCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    description: Annotated[str | None, BeforeValidator(blank_to_none)] = Field(
        default=None, max_length=2000
    )
    event_type: FarmEventType
    event_date: date
    start_time: time
    end_time: time
    # Per person, in whole cents. Zero is allowed for free experiences.
    price: PriceOrFree
    capacity: int = Field(gt=0, le=MAX_EVENT_CAPACITY)

    @model_validator(mode="after")
    def ends_after_it_starts(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class FarmEventRead(BaseModel):
    id: int
    farm_id: int
    title: str
    description: str | None
    event_type: FarmEventType
    event_date: date
    start_time: time
    end_time: time
    price: Decimal
    capacity: int
    # Capacity minus the party sizes of every reservation that is not cancelled.
    spots_remaining: int
    created_at: datetime

    @classmethod
    def from_event(cls, event: FarmEvent, reserved_spots: int) -> Self:
        return cls(
            id=event.id,
            farm_id=event.farm_id,
            title=event.title,
            description=event.description,
            event_type=event.event_type,
            event_date=event.event_date,
            start_time=event.start_time,
            end_time=event.end_time,
            price=event.price,
            capacity=event.capacity,
            spots_remaining=event.capacity - reserved_spots,
            created_at=event.created_at,
        )


class EventSearchParams(NearbySearchParams):
    """Query parameters of the search for upcoming farm experiences."""

    event_type: FarmEventType | None = None


class EventSearchFarm(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_name: str
    city: str
    state: str


class EventSearchResult(BaseModel):
    event: FarmEventRead
    farm: EventSearchFarm
    distance_miles: float


class EventReservationCreate(BaseModel):
    event_id: DatabaseId
    party_size: int = Field(gt=0, le=MAX_EVENT_CAPACITY)


class ReservedEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    event_type: FarmEventType
    event_date: date
    start_time: time
    end_time: time
    price: Decimal


class EventReservationRead(BaseModel):
    id: int
    party_size: int
    status: ReservationStatus
    created_at: datetime
    # The name is all a farmer is shown about the customer.
    customer_name: str
    event: ReservedEvent
    farm: ReservationFarm

    @classmethod
    def from_reservation(cls, reservation: EventReservation) -> Self:
        return cls(
            id=reservation.id,
            party_size=reservation.party_size,
            status=reservation.status,
            created_at=reservation.created_at,
            customer_name=reservation.customer.name,
            event=ReservedEvent.model_validate(reservation.event),
            farm=ReservationFarm.from_farm(reservation.event.farm),
        )
