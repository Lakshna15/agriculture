import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_check_constraint


class NotificationType(enum.StrEnum):
    GROW_OFFER_CONFIRMED = "GROW_OFFER_CONFIRMED"
    CROP_UPDATE_POSTED = "CROP_UPDATE_POSTED"
    CROP_READY = "CROP_READY"
    GROW_OFFER_CANCELLED = "GROW_OFFER_CANCELLED"


class Notification(Base):
    """An in-app message for one user. Nothing is sent outside the application."""

    __tablename__ = "notifications"
    __table_args__ = (
        enum_check_constraint("type", NotificationType),
        # A user's notifications are always read newest first.
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, native_enum=False, length=30)
    )
    message: Mapped[str] = mapped_column(String(500))
    read: Mapped[bool] = mapped_column(server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
