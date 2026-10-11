import enum
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, enum_check_constraint
from app.models.reservation import ReservationStatus

if TYPE_CHECKING:
    from app.models.farm import Farm
    from app.models.user import User


class FarmEventType(enum.StrEnum):
    STRAWBERRY_PICKING = "STRAWBERRY_PICKING"
    APPLE_PICKING = "APPLE_PICKING"
    PUMPKIN_PICKING = "PUMPKIN_PICKING"
    VEGETABLE_PICKING = "VEGETABLE_PICKING"
    FARM_TOUR = "FARM_TOUR"
    OTHER = "OTHER"


class FarmEvent(Base):
    """A farm experience customers can book, such as a pick-your-own day or a tour."""

    __tablename__ = "farm_events"
    __table_args__ = (
        enum_check_constraint("event_type", FarmEventType),
        CheckConstraint("end_time > start_time", name="ends_after_it_starts"),
        CheckConstraint("price >= 0", name="price_not_negative"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[FarmEventType] = mapped_column(
        Enum(FarmEventType, native_enum=False, length=30)
    )
    event_date: Mapped[date] = mapped_column(index=True)
    start_time: Mapped[time]
    end_time: Mapped[time]
    # Per person. Zero means the experience is free.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # The most people that may be booked across all reservations.
    capacity: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    farm: Mapped["Farm"] = relationship()


class EventReservation(Base):
    __tablename__ = "event_reservations"
    __table_args__ = (
        CheckConstraint("party_size > 0", name="party_size_positive"),
        enum_check_constraint("status", ReservationStatus),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("farm_events.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Counts against the event's capacity until the reservation is cancelled.
    party_size: Mapped[int]
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, native_enum=False, length=20),
        server_default=ReservationStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    event: Mapped["FarmEvent"] = relationship()
    customer: Mapped["User"] = relationship()
