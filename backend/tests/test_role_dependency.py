from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User, UserRole
from tests.helpers import auth_headers, create_user


@pytest.fixture
def role_probe_client(db_session: Session) -> Iterator[TestClient]:
    """A minimal app with role-protected routes, so the dependency is tested on its own."""
    probe_app = FastAPI()

    @probe_app.get("/farmer-only")
    def farmer_only(
        user: Annotated[User, Depends(require_role(UserRole.FARMER))],
    ) -> dict[str, str]:
        return {"role": user.role}

    @probe_app.get("/customer-or-admin")
    def customer_or_admin(
        user: Annotated[User, Depends(require_role(UserRole.CUSTOMER, UserRole.ADMIN))],
    ) -> dict[str, str]:
        return {"role": user.role}

    probe_app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(probe_app) as test_client:
        yield test_client


def test_user_with_the_required_role_is_admitted(
    role_probe_client: TestClient, db_session: Session
) -> None:
    farmer = create_user(db_session, role=UserRole.FARMER, email="farmer@example.com")

    response = role_probe_client.get("/farmer-only", headers=auth_headers(farmer))

    assert response.status_code == 200
    assert response.json() == {"role": "FARMER"}


@pytest.mark.parametrize("role", [UserRole.CUSTOMER, UserRole.ADMIN])
def test_user_with_another_role_is_forbidden(
    role_probe_client: TestClient, db_session: Session, role: UserRole
) -> None:
    user = create_user(db_session, role=role, email="other@example.com")

    response = role_probe_client.get("/farmer-only", headers=auth_headers(user))

    assert response.status_code == 403
    assert response.json() == {"detail": "You do not have permission to perform this action"}


def test_unauthenticated_request_is_rejected_before_the_role_check(
    role_probe_client: TestClient,
) -> None:
    response = role_probe_client.get("/farmer-only")

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [(UserRole.CUSTOMER, 200), (UserRole.ADMIN, 200), (UserRole.FARMER, 403)],
)
def test_dependency_accepts_any_of_several_roles(
    role_probe_client: TestClient, db_session: Session, role: UserRole, expected_status: int
) -> None:
    user = create_user(db_session, role=role, email="member@example.com")

    response = role_probe_client.get("/customer-or-admin", headers=auth_headers(user))

    assert response.status_code == expected_status
