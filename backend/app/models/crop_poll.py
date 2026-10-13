import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, enum_check_constraint

if TYPE_CHECKING:
    from app.models.farm import Farm


class CropPollStatus(enum.StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CropPoll(Base):
    """A farmer asking nearby customers what to grow next."""

    __tablename__ = "crop_polls"
    __table_args__ = (enum_check_constraint("status", CropPollStatus),)

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    question: Mapped[str] = mapped_column(String(200))
    status: Mapped[CropPollStatus] = mapped_column(
        Enum(CropPollStatus, native_enum=False, length=20),
        server_default=CropPollStatus.OPEN.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    farm: Mapped["Farm"] = relationship()
    options: Mapped[list["CropPollOption"]] = relationship(
        back_populates="poll", order_by="CropPollOption.id"
    )


class CropPollOption(Base):
    __tablename__ = "crop_poll_options"
    __table_args__ = (
        UniqueConstraint("poll_id", "crop_name", name="uq_crop_poll_options_poll_id_crop_name"),
        # Lets a vote reference (poll_id, option_id) together; see CropVote.
        UniqueConstraint("poll_id", "id", name="uq_crop_poll_options_poll_id_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("crop_polls.id"), index=True)
    crop_name: Mapped[str] = mapped_column(String(80))

    poll: Mapped["CropPoll"] = relationship(back_populates="options")


class CropVote(Base):
    __tablename__ = "crop_votes"
    __table_args__ = (
        # A customer casts one vote per poll.
        UniqueConstraint("poll_id", "customer_id", name="uq_crop_votes_poll_id_customer_id"),
        # The chosen option must be one of this poll's own options. Referencing
        # the pair makes the database refuse a vote that names an option from
        # a different poll.
        ForeignKeyConstraint(
            ["poll_id", "option_id"],
            ["crop_poll_options.poll_id", "crop_poll_options.id"],
            name="fk_crop_votes_poll_id_option_id_crop_poll_options",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("crop_polls.id"), index=True)
    option_id: Mapped[int]
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
