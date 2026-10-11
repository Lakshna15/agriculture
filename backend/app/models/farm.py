from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, Computed, Double, ForeignKey, Index, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Farm(TimestampMixin, Base):
    __tablename__ = "farms"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        Index("ix_farms_location", "location", postgresql_using="gist"),
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

    # The point PostGIS searches by distance. PostgreSQL derives it from
    # latitude and longitude, so the two representations can never disagree
    # and no application code has to keep them in step. It is deferred because
    # it is only ever used inside spatial queries, never read as a value.
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        Computed("ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography", persisted=True),
        deferred=True,
    )
