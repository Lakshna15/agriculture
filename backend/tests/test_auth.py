from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User, UserRole
from app.services.security import JWT_ALGORITHM, verify_password
from tests.helpers import DEFAULT_PASSWORD, auth_headers, create_user

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"


def registration_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "name": "Ana Grower",
        "email": "ana@example.com",
        "password": DEFAULT_PASSWORD,
        "role": "CUSTOMER",
    }
    return payload | overrides


def count_users(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(User)) or 0


def contains_password_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            "password" in key.lower() or contains_password_field(nested)
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return any(contains_password_field(item) for item in value)
    return False


class TestRegistration:
    def test_customer_can_register(self, client: TestClient, db_session: Session) -> None:
        response = client.post(REGISTER_URL, json=registration_payload(role="CUSTOMER"))

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Ana Grower"
        assert body["email"] == "ana@example.com"
        assert body["role"] == "CUSTOMER"

        stored_user = db_session.get(User, body["id"])
        assert stored_user is not None
        assert stored_user.role is UserRole.CUSTOMER

    def test_farmer_can_register(self, client: TestClient, db_session: Session) -> None:
        response = client.post(REGISTER_URL, json=registration_payload(role="FARMER"))

        assert response.status_code == 201
        assert response.json()["role"] == "FARMER"

        stored_user = db_session.get(User, response.json()["id"])
        assert stored_user is not None
        assert stored_user.role is UserRole.FARMER

    def test_admin_registration_is_rejected(self, client: TestClient, db_session: Session) -> None:
        response = client.post(REGISTER_URL, json=registration_payload(role="ADMIN"))

        assert response.status_code == 422
        assert count_users(db_session) == 0

    def test_duplicate_email_is_rejected(self, client: TestClient, db_session: Session) -> None:
        first_response = client.post(REGISTER_URL, json=registration_payload())
        second_response = client.post(REGISTER_URL, json=registration_payload(name="Someone Else"))

        assert first_response.status_code == 201
        assert second_response.status_code == 409
        assert second_response.json() == {"detail": "An account with this email already exists"}
        assert count_users(db_session) == 1

    def test_duplicate_email_differing_only_by_case_is_rejected(self, client: TestClient) -> None:
        client.post(REGISTER_URL, json=registration_payload(email="ana@example.com"))

        response = client.post(REGISTER_URL, json=registration_payload(email="ANA@Example.com"))

        assert response.status_code == 409

    def test_email_is_normalized_before_it_is_stored(
        self, client: TestClient, db_session: Session
    ) -> None:
        response = client.post(
            REGISTER_URL, json=registration_payload(email="  Ana.Grower@Example.COM  ")
        )

        assert response.status_code == 201
        assert response.json()["email"] == "ana.grower@example.com"
        stored_user = db_session.get(User, response.json()["id"])
        assert stored_user is not None
        assert stored_user.email == "ana.grower@example.com"

    def test_password_is_stored_as_an_argon2_hash(
        self, client: TestClient, db_session: Session
    ) -> None:
        response = client.post(REGISTER_URL, json=registration_payload())

        stored_user = db_session.get(User, response.json()["id"])
        assert stored_user is not None
        assert stored_user.password_hash != DEFAULT_PASSWORD
        assert stored_user.password_hash.startswith("$argon2id$")
        assert verify_password(DEFAULT_PASSWORD, stored_user.password_hash)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"password": "short"},
            {"email": "not-an-email"},
            {"name": "   "},
            {"role": "customer"},
            {"role": None},
        ],
        ids=["short password", "invalid email", "blank name", "lowercase role", "missing role"],
    )
    def test_invalid_registration_is_rejected(
        self, client: TestClient, db_session: Session, overrides: dict[str, Any]
    ) -> None:
        response = client.post(REGISTER_URL, json=registration_payload(**overrides))

        assert response.status_code == 422
        assert count_users(db_session) == 0


class TestLogin:
    def test_login_returns_an_access_token_and_the_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        user = create_user(db_session, role=UserRole.FARMER, email="farmer@example.com")

        response = client.post(
            LOGIN_URL, json={"email": "farmer@example.com", "password": DEFAULT_PASSWORD}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["user"]["id"] == user.id
        assert body["user"]["role"] == "FARMER"

        me_response = client.get(ME_URL, headers={"Authorization": f"Bearer {body['access_token']}"})
        assert me_response.status_code == 200
        assert me_response.json()["id"] == user.id

    def test_login_ignores_email_case(self, client: TestClient, db_session: Session) -> None:
        create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")

        response = client.post(
            LOGIN_URL, json={"email": "Ana@Example.com", "password": DEFAULT_PASSWORD}
        )

        assert response.status_code == 200

    def test_wrong_password_is_rejected(self, client: TestClient, db_session: Session) -> None:
        create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")

        response = client.post(
            LOGIN_URL, json={"email": "ana@example.com", "password": "not-the-password"}
        )

        assert response.status_code == 401
        assert response.json() == {"detail": "Incorrect email or password"}
        assert "access_token" not in response.json()

    def test_password_whitespace_is_significant(self, client: TestClient) -> None:
        padded_password = "  spaces are part of it  "
        client.post(REGISTER_URL, json=registration_payload(password=padded_password))

        exact_response = client.post(
            LOGIN_URL, json={"email": "ana@example.com", "password": padded_password}
        )
        trimmed_response = client.post(
            LOGIN_URL, json={"email": "ana@example.com", "password": padded_password.strip()}
        )

        assert exact_response.status_code == 200
        assert trimmed_response.status_code == 401

    def test_unknown_email_gets_the_same_response_as_a_wrong_password(
        self, client: TestClient
    ) -> None:
        response = client.post(
            LOGIN_URL, json={"email": "nobody@example.com", "password": DEFAULT_PASSWORD}
        )

        assert response.status_code == 401
        assert response.json() == {"detail": "Incorrect email or password"}


class TestCurrentUser:
    def test_unauthenticated_request_is_rejected(self, client: TestClient) -> None:
        response = client.get(ME_URL)

        assert response.status_code == 401
        assert response.json() == {"detail": "Not authenticated"}
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_authenticated_request_returns_the_user(
        self, client: TestClient, db_session: Session
    ) -> None:
        user = create_user(
            db_session, role=UserRole.CUSTOMER, email="ana@example.com", name="Ana Grower"
        )

        response = client.get(ME_URL, headers=auth_headers(user))

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == user.id
        assert body["name"] == "Ana Grower"
        assert body["email"] == "ana@example.com"
        assert body["role"] == "CUSTOMER"

    def test_malformed_token_is_rejected(self, client: TestClient) -> None:
        response = client.get(ME_URL, headers={"Authorization": "Bearer not-a-jwt"})

        assert response.status_code == 401

    def test_expired_token_is_rejected(self, client: TestClient, db_session: Session) -> None:
        user = create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")
        expired_token = jwt.encode(
            {"sub": str(user.id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
            get_settings().jwt_secret_key.get_secret_value(),
            algorithm=JWT_ALGORITHM,
        )

        response = client.get(ME_URL, headers={"Authorization": f"Bearer {expired_token}"})

        assert response.status_code == 401

    def test_token_signed_with_another_key_is_rejected(
        self, client: TestClient, db_session: Session
    ) -> None:
        user = create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")
        forged_token = jwt.encode(
            {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=5)},
            "a-different-signing-key-of-sufficient-length",
            algorithm=JWT_ALGORITHM,
        )

        response = client.get(ME_URL, headers={"Authorization": f"Bearer {forged_token}"})

        assert response.status_code == 401

    def test_unsigned_token_is_rejected(self, client: TestClient, db_session: Session) -> None:
        user = create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")
        unsigned_token = jwt.encode(
            {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=5)},
            key=None,
            algorithm="none",
        )

        response = client.get(ME_URL, headers={"Authorization": f"Bearer {unsigned_token}"})

        assert response.status_code == 401

    def test_token_for_a_deleted_user_is_rejected(
        self, client: TestClient, db_session: Session
    ) -> None:
        user = create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")
        headers = auth_headers(user)
        db_session.delete(user)
        db_session.commit()

        response = client.get(ME_URL, headers=headers)

        assert response.status_code == 401


def test_password_hash_is_never_returned(client: TestClient) -> None:
    register_response = client.post(REGISTER_URL, json=registration_payload())
    login_response = client.post(
        LOGIN_URL, json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )
    access_token = login_response.json()["access_token"]
    me_response = client.get(ME_URL, headers={"Authorization": f"Bearer {access_token}"})

    for response in (register_response, login_response, me_response):
        assert response.is_success
        assert not contains_password_field(response.json())
        assert DEFAULT_PASSWORD not in response.text
        assert "$argon2" not in response.text
