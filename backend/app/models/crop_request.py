import enum
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    Double,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_check_constraint
from app.models.product import ProductUnit


class RequestFrequency(enum.StrEnum):
    ONE_TIME = "ONE_TIME"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class Season(enum.StrEnum):
    SPRING = "SPRING"
    SUMMER = "SUMMER"
    FALL = "FALL"
    WINTER = "WINTER"


class CropRequestStatus(enum.StrEnum):
    OPEN = "OPEN"
    CANCELLED = "CANCELLED"


class CropRequest(Base):
    """A customer asking nearby farmers to grow a crop they could not find."""

    __tablename__ = "crop_requests"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("radius_miles BETWEEN 1 AND 500", name="radius_range"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        enum_check_constraint("unit", ProductUnit),
        enum_check_constraint("frequency", RequestFrequency),
        enum_check_constraint("preferred_season", Season),
        enum_check_constraint("status", CropRequestStatus),
        Index(
            "ix_crop_requests_approximate_location",
            "approximate_location",
            postgresql_using="gist",
        ),
        # A customer has at most one open request per crop. Without this,
        # repeating a request would inflate the demand farmers are shown.
        Index(
            "uq_crop_requests_open_customer_crop",
            "customer_id",
            "crop_name",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Stored in one canonical spelling so that requests for the same crop group together.
    crop_name: Mapped[str] = mapped_column(String(80), index=True)
    quantity: Mapped[int]
    unit: Mapped[ProductUnit] = mapped_column(Enum(ProductUnit, native_enum=False, length=20))
    # How often the customer wants `quantity`.
    frequency: Mapped[RequestFrequency] = mapped_column(
        Enum(RequestFrequency, native_enum=False, length=20)
    )
    # Where the customer is and how far they will travel. These are private to
    # the customer and are never returned to farmers.
    latitude: Mapped[float] = mapped_column(Double)
    longitude: Mapped[float] = mapped_column(Double)
    radius_miles: Mapped[int]
    preferred_season: Mapped[Season | None] = mapped_column(
        Enum(Season, native_enum=False, length=20)
    )
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CropRequestStatus] = mapped_column(
        Enum(CropRequestStatus, native_enum=False, length=20),
        server_default=CropRequestStatus.OPEN.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # The point used to decide which farms a request is near. It is the
    # customer's location rounded to two decimal places, a cell roughly 0.7
    # miles across. Matching on the rounded point means that even a farmer who
    # moves their farm repeatedly to probe where demand appears and disappears
    # can narrow a customer down only to that cell, never to an address.
    approximate_location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        Computed(
            "ST_SetSRID(ST_MakePoint("
            "round(longitude::numeric, 2)::double precision, "
            "round(latitude::numeric, 2)::double precision"
            "), 4326)::geography",
            persisted=True,
        ),
        deferred=True,
    )
