import enum
from datetime import date, datetime
from decimal import Decimal

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text, false, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, enum_check_constraint

if TYPE_CHECKING:
    from app.models.farm import Farm


class ProductCategory(enum.StrEnum):
    VEGETABLES = "VEGETABLES"
    FRUITS = "FRUITS"
    EGGS = "EGGS"
    DAIRY = "DAIRY"
    MEAT = "MEAT"
    HERBS = "HERBS"
    SEASONAL = "SEASONAL"
    OTHER = "OTHER"


class ProductUnit(enum.StrEnum):
    LB = "LB"
    OZ = "OZ"
    EACH = "EACH"
    DOZEN = "DOZEN"
    BUNCH = "BUNCH"
    PINT = "PINT"
    QUART = "QUART"
    GALLON = "GALLON"


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        enum_check_constraint("category", ProductCategory),
        enum_check_constraint("unit", ProductUnit),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("quantity_available >= 0", name="quantity_not_negative"),
        CheckConstraint(
            "available_until IS NULL OR available_from IS NULL OR available_until >= available_from",
            name="availability_window_ordered",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[ProductCategory] = mapped_column(
        Enum(ProductCategory, native_enum=False, length=20)
    )
    description: Mapped[str | None] = mapped_column(Text)
    # Money is stored as an exact decimal, never as a binary float.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit: Mapped[ProductUnit] = mapped_column(Enum(ProductUnit, native_enum=False, length=20))
    # A whole number of `unit`. It is changed only through
    # services.products.change_product_quantity, which records the history row.
    quantity_available: Mapped[int] = mapped_column(server_default="0")
    harvest_date: Mapped[date | None]
    # An open end means no limit on that side of the availability window.
    available_from: Mapped[date | None]
    available_until: Mapped[date | None]
    organic: Mapped[bool] = mapped_column(server_default=false())
    # Inactive products stay in the farmer's list but are hidden from customers.
    active: Mapped[bool] = mapped_column(server_default=true())

    farm: Mapped["Farm"] = relationship()


class InventoryHistory(Base):
    """One row per change to a product's quantity, forming its stock audit trail."""

    __tablename__ = "inventory_history"
    __table_args__ = (
        CheckConstraint(
            "previous_quantity >= 0 AND new_quantity >= 0", name="quantities_not_negative"
        ),
        CheckConstraint("previous_quantity <> new_quantity", name="quantity_changed"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    previous_quantity: Mapped[int]
    new_quantity: Mapped[int]
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
