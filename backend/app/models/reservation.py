import enum
from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, enum_check_constraint

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class ReservationStatus(enum.StrEnum):
    """Lifecycle shared by product reservations and event reservations."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ProductReservation(TimestampMixin, Base):
    __tablename__ = "product_reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        enum_check_constraint("status", ReservationStatus),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    # Deducted from the product's stock when the reservation is made and
    # returned to it if the reservation is cancelled.
    quantity: Mapped[int]
    pickup_date: Mapped[date]
    pickup_time: Mapped[time]
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, native_enum=False, length=20),
        server_default=ReservationStatus.PENDING.value,
    )

    customer: Mapped["User"] = relationship()
    product: Mapped["Product"] = relationship()
