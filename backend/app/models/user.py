import enum

from sqlalchemy import CheckConstraint, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, enum_check_constraint


class UserRole(enum.StrEnum):
    CUSTOMER = "CUSTOMER"
    FARMER = "FARMER"
    ADMIN = "ADMIN"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # Emails are compared case-insensitively. Storing only the normalized
        # form lets the plain unique constraint enforce that at database level.
        CheckConstraint("email = lower(btrim(email))", name="email_normalized"),
        enum_check_constraint("role", UserRole),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False, length=20))
