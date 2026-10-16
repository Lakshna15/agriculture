import enum
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_check_constraint


class ApplicationEventType(enum.StrEnum):
    SEARCH_PERFORMED = "SEARCH_PERFORMED"
    NO_SEARCH_RESULT = "NO_SEARCH_RESULT"
    PRODUCT_VIEWED = "PRODUCT_VIEWED"
    FARM_VIEWED = "FARM_VIEWED"
    CROP_REQUESTED = "CROP_REQUESTED"
    GROW_OFFER_CREATED = "GROW_OFFER_CREATED"
    CROP_COMMITTED = "CROP_COMMITTED"
    RESERVATION_CREATED = "RESERVATION_CREATED"
    INVENTORY_UPDATED = "INVENTORY_UPDATED"
    FARM_EVENT_BOOKED = "FARM_EVENT_BOOKED"


class ApplicationEvent(Base):
    """Something that happened in the marketplace, recorded for analytics.

    Events are append-only and are read by the data pipeline, never by the
    API. They hold ids and small facts about the action, not personal details:
    no names, emails, notes or exact customer coordinates.
    """

    __tablename__ = "application_events"
    __table_args__ = (
        enum_check_constraint("event_type", ApplicationEventType),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_is_object"),
        # The pipeline reads events in time order.
        Index("ix_application_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_type: Mapped[ApplicationEventType] = mapped_column(
        Enum(ApplicationEventType, native_enum=False, length=40)
    )
    # Links are cleared rather than blocking a delete, so analytics history
    # never stands in the way of removing a user, farm or product.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id", ondelete="SET NULL"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    # "metadata" is reserved on declarative classes, so the attribute has another name.
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
