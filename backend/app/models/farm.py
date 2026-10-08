from sqlalchemy import CheckConstraint, Double, ForeignKey, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Farm(TimestampMixin, Base):
    __tablename__ = "farms"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # A farmer owns at most one farm. The unique constraint is what enforces
    # it, so two simultaneous create requests cannot both succeed.
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    farm_name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    zip_code: Mapped[str] = mapped_column(String(10))
    # WGS 84 decimal degrees, the coordinate system GPS and web maps use.
    latitude: Mapped[float] = mapped_column(Double)
    longitude: Mapped[float] = mapped_column(Double)
    phone: Mapped[str | None] = mapped_column(String(30))
    pickup_available: Mapped[bool] = mapped_column(server_default=true())
    delivery_available: Mapped[bool] = mapped_column(server_default=false())
