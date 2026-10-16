"""Protections that apply to the whole API rather than to one feature."""

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.log_redaction import ACCESS_LOGGER_NAME, QueryStringRedactingFilter
from app.main import app
from app.middleware.body_size_limit import MAX_REQUEST_BODY_BYTES
from app.models.user import User, UserRole
from app.services.security import JWT_ALGORITHM
from tests.helpers import DEFAULT_PASSWORD, create_user

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"


def count_users(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(User)) or 0


class TestValidationErrors:
    def test_a_rejected_password_is_not_sent_back(self, client: TestClient) -> None:
        response = client.post(
            REGISTER_URL,
            json={"name": "Ana", "email": "ana@example.com", "password": "hunter2", "role": "CUSTOMER"},
        )

        assert response.status_code == 422
        assert "hunter2" not in response.text

    def test_each_issue_says_where_and_what_without_the_value(self, client: TestClient) -> None:
        response = client.post(
            REGISTER_URL,
            json={"name": "Ana", "email": "not-an-email", "password": "short", "role": "ADMIN"},
        )

        issues = response.json()["detail"]
        assert {tuple(issue["loc"]) for issue in issues} == {
            ("body", "email"),
            ("body", "password"),
            ("body", "role"),
        }
        for issue in issues:
            assert set(issue) == {"type", "loc", "msg"}

    def test_an_oversized_field_is_not_echoed_back(self, client: TestClient) -> None:
        long_name = "a" * 50_000

        response = client.post(
            REGISTER_URL,
            json={"name": long_name, "email": "ana@example.com", "password": DEFAULT_PASSWORD, "role": "CUSTOMER"},
        )

        assert response.status_code == 422
        assert len(response.content) < 1_000

    def test_malformed_json_is_a_validation_error(self, client: TestClient) -> None:
        response = client.post(
            LOGIN_URL, content="{not json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422
        assert response.json()["detail"][0]["type"] == "json_invalid"

    def test_invalid_query_parameters_get_the_same_shape(self, client: TestClient) -> None:
        response = client.get("/api/products/search", params={"latitude": "north", "longitude": 0})

        assert response.status_code == 422
        assert set(response.json()["detail"][0]) == {"type", "loc", "msg"}


class TestUnexpectedErrors:
    @pytest.fixture
    def failing_client(self) -> Iterator[TestClient]:
        def broken_database() -> Iterator[None]:
            raise RuntimeError("connection string postgres://admin:secret@db/internal")
            yield  # makes this a generator dependency, like the real one

        app.dependency_overrides[get_db] = broken_database
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
        app.dependency_overrides.clear()

    def test_an_unexpected_error_is_a_plain_json_500(self, failing_client: TestClient) -> None:
        response = failing_client.get("/health")

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
        for name, value in TestSecurityHeaders.EXPECTED.items():
            assert response.headers[name] == value

    def test_the_cause_is_logged_but_not_returned(
        self, failing_client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR, logger="app.errors"):
            response = failing_client.get("/health")

        assert "secret" not in response.text
        assert "Traceback" not in response.text
        assert "RuntimeError" not in response.text
        assert any("Unhandled error while serving GET /health" in record.message for record in caplog.records)


class TestSecurityHeaders:
    EXPECTED = {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "no-referrer",
        "cache-control": "no-store",
    }

    @pytest.mark.parametrize(
        ("method", "path", "expected_status"),
        [
            ("GET", "/health", 200),
            ("GET", "/api/auth/me", 401),
            ("GET", "/api/farms/999999", 404),
            ("POST", "/api/auth/login", 422),
        ],
    )
    def test_every_response_carries_the_security_headers(
        self, client: TestClient, method: str, path: str, expected_status: int
    ) -> None:
        response = client.request(method, path, json={} if method == "POST" else None)

        assert response.status_code == expected_status
        for name, value in self.EXPECTED.items():
            assert response.headers[name] == value


class TestRequestBodySizeLimit:
    def test_a_body_declared_over_the_limit_is_refused_before_it_is_read(
        self, client: TestClient, db_session: Session
    ) -> None:
        payload = json.dumps(
            {
                "name": "a" * MAX_REQUEST_BODY_BYTES,
                "email": "ana@example.com",
                "password": DEFAULT_PASSWORD,
                "role": "CUSTOMER",
            }
        )

        response = client.post(
            REGISTER_URL, content=payload, headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 413
        assert response.json() == {"detail": "Request body is too large"}
        assert response.headers["x-content-type-options"] == "nosniff"
        assert count_users(db_session) == 0

    def test_a_streamed_body_over_the_limit_is_refused(
        self, client: TestClient, db_session: Session
    ) -> None:
        def chunks() -> Iterator[bytes]:
            # Sent without a Content-Length, so only counting the bytes can catch it.
            yield b'{"name": "'
            for _ in range(MAX_REQUEST_BODY_BYTES // 65_536 + 2):
                yield b"a" * 65_536
            yield b'", "email": "ana@example.com", "password": "x", "role": "CUSTOMER"}'

        response = client.post(
            REGISTER_URL, content=chunks(), headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 413
        assert count_users(db_session) == 0

    def test_a_streamed_body_within_the_limit_is_passed_on_intact(
        self, client: TestClient, db_session: Session
    ) -> None:
        body = json.dumps(
            {"name": "Ana", "email": "ana@example.com", "password": DEFAULT_PASSWORD, "role": "CUSTOMER"}
        ).encode()

        def chunks() -> Iterator[bytes]:
            for start in range(0, len(body), 7):
                yield body[start : start + 7]

        response = client.post(
            REGISTER_URL, content=chunks(), headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 201
        assert count_users(db_session) == 1


class TestCrossOriginRequests:
    def test_responses_grant_no_other_origin_access(self, client: TestClient) -> None:
        response = client.get("/health", headers={"Origin": "https://another-site.example"})

        assert "access-control-allow-origin" not in response.headers

    def test_cross_origin_preflight_is_not_approved(self, client: TestClient) -> None:
        response = client.options(
            LOGIN_URL,
            headers={
                "Origin": "https://another-site.example",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 405
        assert "access-control-allow-origin" not in response.headers


class TestLoginThrottling:
    def wrong_password(self, client: TestClient, email: str = "ana@example.com"):
        return client.post(LOGIN_URL, json={"email": email, "password": "not-the-password"})

    def test_an_account_is_locked_after_five_failed_attempts(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")
        statuses = [self.wrong_password(client).status_code for _ in range(5)]

        locked = client.post(LOGIN_URL, json={"email": "ana@example.com", "password": DEFAULT_PASSWORD})

        assert statuses == [401] * 5
        # Refused even with the right password, so a lucky guess learns nothing.
        assert locked.status_code == 429
        assert locked.json() == {"detail": "Too many failed login attempts. Please wait and try again."}
        assert 0 < int(locked.headers["Retry-After"]) <= 15 * 60
        assert "access_token" not in locked.text

    def test_the_lock_applies_whatever_case_the_email_is_typed_in(
        self, client: TestClient, db_session: Session
    ) -> None:
        for _ in range(5):
            self.wrong_password(client, email="ana@example.com")

        response = self.wrong_password(client, email="ANA@Example.com")

        assert response.status_code == 429

    def test_other_accounts_are_not_affected(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_user(db_session, role=UserRole.CUSTOMER, email="ben@example.com")
        for _ in range(5):
            self.wrong_password(client, email="ana@example.com")

        response = client.post(LOGIN_URL, json={"email": "ben@example.com", "password": DEFAULT_PASSWORD})

        assert response.status_code == 200

    def test_a_successful_login_resets_the_count(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_user(db_session, role=UserRole.CUSTOMER, email="ana@example.com")
        for _ in range(4):
            self.wrong_password(client)
        assert client.post(
            LOGIN_URL, json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
        ).status_code == 200

        statuses = [self.wrong_password(client).status_code for _ in range(4)]

        assert statuses == [401] * 4


class TestAccessLogRedaction:
    def access_record(self, path: str) -> logging.LogRecord:
        return logging.LogRecord(
            name=ACCESS_LOGGER_NAME,
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("172.20.0.1:5000", "GET", path, "1.1", 200),
            exc_info=None,
        )

    def test_search_coordinates_are_removed_from_the_access_log(self) -> None:
        record = self.access_record("/api/products/search?latitude=35.2271&longitude=-80.8431")

        QueryStringRedactingFilter().filter(record)

        message = record.getMessage()
        assert "35.2271" not in message
        assert "-80.8431" not in message
        assert "GET /api/products/search?[redacted] HTTP/1.1" in message

    def test_a_path_without_a_query_is_logged_as_it_is(self) -> None:
        record = self.access_record("/api/auth/me")

        QueryStringRedactingFilter().filter(record)

        assert "GET /api/auth/me HTTP/1.1" in record.getMessage()

    def test_the_filter_is_installed_on_uvicorns_access_logger(self) -> None:
        filters = logging.getLogger(ACCESS_LOGGER_NAME).filters

        assert any(isinstance(installed, QueryStringRedactingFilter) for installed in filters)


class TestStartupConfiguration:
    def settings_with_key(self, key: str) -> Settings:
        return Settings(jwt_secret_key=SecretStr(key))

    def test_the_example_placeholder_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="replace the example JWT_SECRET_KEY"):
            self.settings_with_key("change_me_replace_with_a_long_random_value")

    def test_a_short_key_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            self.settings_with_key("too-short")

    def test_a_refused_key_from_the_environment_is_not_repeated_in_the_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JWT_SECRET_KEY", "a-real-key-that-is-short")

        with pytest.raises(ValidationError) as refused:
            Settings()

        assert "jwt_secret_key" in str(refused.value)
        assert "a-real-key-that-is-short" not in str(refused.value)

    def test_an_unknown_marketplace_time_zone_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="unknown time zone: Mars/Olympus_Mons"):
            Settings(
                jwt_secret_key=SecretStr("q8Vb3-Lx0pR2sK9mZt7wYc4nHa6uJe1f"),
                marketplace_timezone="Mars/Olympus_Mons",
            )

    def test_a_long_random_key_is_accepted(self) -> None:
        settings = self.settings_with_key("q8Vb3-Lx0pR2sK9mZt7wYc4nHa6uJe1f")

        assert len(settings.jwt_secret_key.get_secret_value()) == 32


@pytest.mark.parametrize("subject", ["0", "-5", "99999999999999999999"])
def test_token_naming_an_impossible_user_id_is_rejected_not_an_error(
    client: TestClient, subject: str
) -> None:
    token = jwt.encode(
        {"sub": subject, "exp": datetime.now(UTC) + timedelta(minutes=5)},
        get_settings().jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
