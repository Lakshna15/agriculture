import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, enum_check_constraint


class CropStage(enum.StrEnum):
    """Where a crop is on its way from plan to harvest. Declared in growing order."""

    PLANNED = "PLANNED"
    PLANTED = "PLANTED"
    GERMINATED = "GERMINATED"
    GROWING = "GROWING"
    FLOWERING = "FLOWERING"
    HARVEST_SOON = "HARVEST_SOON"
    READY = "READY"


class CropUpdate(Base):
    """One entry in a grow offer's crop journey, posted by the farmer."""

    __tablename__ = "crop_updates"
    __table_args__ = (enum_check_constraint("stage", CropStage),)

    id: Mapped[int] = mapped_column(primary_key=True)
    grow_offer_id: Mapped[int] = mapped_column(ForeignKey("grow_offers.id"), index=True)
    stage: Mapped[CropStage] = mapped_column(Enum(CropStage, native_enum=False, length=20))
    message: Mapped[str] = mapped_column(Text)
    # A link to a photo hosted elsewhere. Nothing is uploaded to Farm2Local.
    image_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
