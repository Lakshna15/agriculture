"""The database, not only the API, must refuse invalid user rows."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import UserRole
from tests.helpers import create_user


def test_database_rejects_a_second_user_with_the_same_email(db_session: Session) -> None:
    create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")

    with pytest.raises(IntegrityError, match="uq_users_email"):
        create_user(db_session, role=UserRole.FARMER, email="ana@example.com")


def test_database_rejects_an_email_that_is_not_normalized(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_users_email_normalized"):
        create_user(db_session, role=UserRole.CUSTOMER, email="Ana@Example.com")


def test_database_rejects_an_unknown_role(db_session: Session) -> None:
    insert_user_with_role = text(
        "INSERT INTO users (name, email, password_hash, role) "
        "VALUES ('Ana', 'ana@example.com', 'not-a-real-hash', :role)"
    )

    with pytest.raises(IntegrityError, match="ck_users_role_allowed"):
        db_session.execute(insert_user_with_role, {"role": "SUPERUSER"})


def test_updated_at_advances_when_a_user_changes(db_session: Session) -> None:
    user = create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")
    created_at = user.created_at

    # now() is fixed for the length of a transaction, and every test runs
    # inside one, so the row is aged first to make the update observable.
    db_session.execute(
        text("UPDATE users SET updated_at = updated_at - interval '1 hour' WHERE id = :id"),
        {"id": user.id},
    )
    db_session.refresh(user)
    aged_updated_at = user.updated_at

    user.name = "Ana Renamed"
    db_session.commit()
    db_session.refresh(user)

    assert user.created_at == created_at
    assert user.updated_at > aged_updated_at
