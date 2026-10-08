import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Explicit constraint names keep migrations deterministic and let later
# migrations alter or drop a constraint by name.
CONSTRAINT_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models; Alembic reads its metadata."""

    metadata = MetaData(naming_convention=CONSTRAINT_NAMING_CONVENTION)


def enum_check_constraint(column_name: str, enum_class: type[enum.Enum]) -> CheckConstraint:
    """Restrict a text column to the values of an enum.

    Enum columns are stored as text with a named CHECK rather than as native
    PostgreSQL enum types, because adding a value is then an ordinary
    constraint change instead of an ALTER TYPE.
    """
    allowed_values = ", ".join(f"'{member.value}'" for member in enum_class)
    return CheckConstraint(f"{column_name} IN ({allowed_values})", name=f"{column_name}_allowed")


class TimestampMixin:
    """Adds created_at and updated_at columns maintained by the database clock."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), sort_order=100
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), sort_order=101
    )
