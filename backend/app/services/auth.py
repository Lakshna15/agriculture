from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import UserRegistration
from app.services.security import hash_password, verify_password

# Verified against when no account matches, so a login attempt costs the same
# whether or not the email is registered and response time does not reveal it.
_UNKNOWN_ACCOUNT_PASSWORD_HASH = hash_password("placeholder for accounts that do not exist")


class EmailAlreadyRegisteredError(Exception):
    """Raised when registration is attempted with an email that already has an account."""


def register_user(db: Session, registration: UserRegistration) -> User:
    user = User(
        name=registration.name,
        email=registration.email,
        password_hash=hash_password(registration.password),
        role=registration.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        # The unique constraint on email is the source of truth. Checking first
        # with a SELECT would still let two simultaneous registrations both pass.
        if isinstance(error.orig, UniqueViolation):
            raise EmailAlreadyRegisteredError(registration.email) from error
        raise
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(password, _UNKNOWN_ACCOUNT_PASSWORD_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
