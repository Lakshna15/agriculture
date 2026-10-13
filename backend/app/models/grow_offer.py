import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, enum_check_constraint
from app.models.product import ProductUnit

if TYPE_CHECKING:
    from app.models.farm import Farm


class GrowOfferStatus(enum.StrEnum):
    OPEN = "OPEN"
    CONFIRMED = "CONFIRMED"
    GROWING = "GROWING"
    READY = "READY"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class GrowOffer(Base):
    """A farmer's offer to grow a crop if enough customers commit to it."""

    __tablename__ = "grow_offers"
    __table_args__ = (
        CheckConstraint("expected_quantity > 0", name="expected_quantity_positive"),
        CheckConstraint("estimated_price > 0", name="estimated_price_positive"),
        CheckConstraint("minimum_customers > 0", name="minimum_customers_positive"),
        CheckConstraint("expected_harvest_date >= planting_date", name="harvest_after_planting"),
        enum_check_constraint("unit", ProductUnit),
        enum_check_constraint("status", GrowOfferStatus),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    crop_name: Mapped[str] = mapped_column(String(80), index=True)
    # The harvest the farmer expects. Commitments cannot add up to more.
    expected_quantity: Mapped[int]
    unit: Mapped[ProductUnit] = mapped_column(Enum(ProductUnit, native_enum=False, length=20))
    # Per unit. An estimate, because the crop does not exist yet.
    estimated_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    planting_date: Mapped[date]
    expected_harvest_date: Mapped[date]
    # The offer is confirmed once this many different customers have committed.
    minimum_customers: Mapped[int]
    status: Mapped[GrowOfferStatus] = mapped_column(
        Enum(GrowOfferStatus, native_enum=False, length=20),
        server_default=GrowOfferStatus.OPEN.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    farm: Mapped["Farm"] = relationship()


class CropCommitment(Base):
    """A customer's promise to take part of a grow offer's harvest."""

    __tablename__ = "crop_commitments"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        # One commitment per customer per offer, so the number of rows for an
        # offer is the number of different customers committed to it.
        UniqueConstraint(
            "grow_offer_id", "customer_id", name="uq_crop_commitments_grow_offer_id_customer_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    grow_offer_id: Mapped[int] = mapped_column(ForeignKey("grow_offers.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    quantity: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    grow_offer: Mapped["GrowOffer"] = relationship()
