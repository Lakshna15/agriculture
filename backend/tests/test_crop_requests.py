from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.crop_request import CropRequest, CropRequestStatus
from app.models.grow_offer import GrowOfferStatus
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_commitment,
    create_crop_request,
    create_farmer_with_farm,
    create_grow_offer,
    create_user,
    crop_request_payload,
)

CROP_REQUESTS_URL = "/api/crop-requests"
MY_CROP_REQUESTS_URL = "/api/crop-requests/mine"


def cancel_url(request_id: int) -> str:
    return f"{CROP_REQUESTS_URL}/{request_id}/cancel"


def count_requests(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(CropRequest)) or 0


@pytest.fixture
def customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="customer@example.com")


@pytest.fixture
def other_customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="other-customer@example.com")


class TestCreateCropRequest:
    def test_customer_requests_a_crop(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        response = client.post(
            CROP_REQUESTS_URL, json=crop_request_payload(), headers=auth_headers(customer)
        )

        assert response.status_code == 201
        body = response.json()
        assert body["crop_name"] == "Okra"
        assert body["quantity"] == 3
        assert body["unit"] == "LB"
        assert body["frequency"] == "WEEKLY"
        assert body["latitude"] == 35.2271
        assert body["longitude"] == -80.8431
        assert body["radius_miles"] == 25
        assert body["preferred_season"] == "SUMMER"
        assert body["notes"] == "For gumbo."
        assert body["status"] == "OPEN"
        assert body["covered_by_commitment"] is False

        stored_request = db_session.get(CropRequest, body["id"])
        assert stored_request is not None
        assert stored_request.customer_id == customer.id

    @pytest.mark.parametrize(
        ("typed", "stored"),
        [
            ("  okra ", "Okra"),
            ("sweet  CORN", "Sweet Corn"),
            ("lamb's lettuce", "Lamb's Lettuce"),
            ("BOK CHOY", "Bok Choy"),
        ],
    )
    def test_crop_name_is_stored_in_one_canonical_spelling(
        self, client: TestClient, customer: User, typed: str, stored: str
    ) -> None:
        response = client.post(
            CROP_REQUESTS_URL,
            json=crop_request_payload(crop_name=typed),
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        assert response.json()["crop_name"] == stored

    def test_season_and_notes_are_optional(self, client: TestClient, customer: User) -> None:
        response = client.post(
            CROP_REQUESTS_URL,
            json=crop_request_payload(preferred_season=None, notes="   "),
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        assert response.json()["preferred_season"] is None
        assert response.json()["notes"] is None

    @pytest.mark.parametrize("role", [UserRole.FARMER, UserRole.ADMIN])
    def test_only_customers_can_request_a_crop(
        self, client: TestClient, db_session: Session, role: UserRole
    ) -> None:
        user = create_user(db_session, role=role, email="not-a-customer@example.com")

        response = client.post(
            CROP_REQUESTS_URL, json=crop_request_payload(), headers=auth_headers(user)
        )

        assert response.status_code == 403
        assert count_requests(db_session) == 0

    def test_unauthenticated_request_is_rejected(
        self, client: TestClient, db_session: Session
    ) -> None:
        response = client.post(CROP_REQUESTS_URL, json=crop_request_payload())

        assert response.status_code == 401
        assert count_requests(db_session) == 0

    def test_customer_and_status_in_the_request_body_are_ignored(
        self, client: TestClient, db_session: Session, customer: User, other_customer: User
    ) -> None:
        response = client.post(
            CROP_REQUESTS_URL,
            json=crop_request_payload(customer_id=other_customer.id, status="CANCELLED"),
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        assert response.json()["status"] == "OPEN"
        stored_request = db_session.get(CropRequest, response.json()["id"])
        assert stored_request is not None
        assert stored_request.customer_id == customer.id

    @pytest.mark.parametrize(
        "overrides",
        [
            {"crop_name": "  "},
            {"crop_name": "x"},
            {"quantity": 0},
            {"quantity": -3},
            {"quantity": 1.5},
            {"unit": "BARREL"},
            {"frequency": "DAILY"},
            {"preferred_season": "MONSOON"},
            {"radius_miles": 0},
            {"radius_miles": 501},
            {"latitude": 91},
            {"longitude": -181},
            {"latitude": None},
        ],
        ids=[
            "blank crop name",
            "one-letter crop name",
            "zero quantity",
            "negative quantity",
            "fractional quantity",
            "unknown unit",
            "unknown frequency",
            "unknown season",
            "zero radius",
            "radius too large",
            "latitude out of range",
            "longitude out of range",
            "missing latitude",
        ],
    )
    def test_invalid_crop_request_is_rejected(
        self, client: TestClient, db_session: Session, customer: User, overrides: dict[str, Any]
    ) -> None:
        response = client.post(
            CROP_REQUESTS_URL,
            json=crop_request_payload(**overrides),
            headers=auth_headers(customer),
        )

        assert response.status_code == 422
        assert count_requests(db_session) == 0


class TestDuplicateCropRequests:
    def test_second_open_request_for_the_same_crop_is_rejected(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        first = client.post(
            CROP_REQUESTS_URL, json=crop_request_payload(), headers=auth_headers(customer)
        )
        # Differs only in spelling, which normalization removes.
        second = client.post(
            CROP_REQUESTS_URL,
            json=crop_request_payload(crop_name=" OKRA ", quantity=50),
            headers=auth_headers(customer),
        )

        assert first.status_code == 201
        assert second.status_code == 409
        assert second.json() == {"detail": "You already have an open request for Okra"}
        assert count_requests(db_session) == 1

    def test_requests_for_different_crops_are_allowed(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        for crop_name in ("Okra", "Collard Greens"):
            response = client.post(
                CROP_REQUESTS_URL,
                json=crop_request_payload(crop_name=crop_name),
                headers=auth_headers(customer),
            )
            assert response.status_code == 201

        assert count_requests(db_session) == 2

    def test_two_customers_can_request_the_same_crop(
        self, client: TestClient, db_session: Session, customer: User, other_customer: User
    ) -> None:
        for requester in (customer, other_customer):
            response = client.post(
                CROP_REQUESTS_URL, json=crop_request_payload(), headers=auth_headers(requester)
            )
            assert response.status_code == 201

        assert count_requests(db_session) == 2

    def test_crop_can_be_requested_again_after_the_first_request_is_cancelled(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        first = client.post(
            CROP_REQUESTS_URL, json=crop_request_payload(), headers=auth_headers(customer)
        )
        client.post(cancel_url(first.json()["id"]), headers=auth_headers(customer))

        second = client.post(
            CROP_REQUESTS_URL, json=crop_request_payload(), headers=auth_headers(customer)
        )

        assert second.status_code == 201
        assert count_requests(db_session) == 2

    def test_database_rejects_a_second_open_request_for_the_same_crop(
        self, db_session: Session, customer: User
    ) -> None:
        create_crop_request(db_session, customer)

        with pytest.raises(IntegrityError, match="uq_crop_requests_open_customer_crop"):
            create_crop_request(db_session, customer, quantity=9)

    def test_database_rejects_a_request_for_nothing(
        self, db_session: Session, customer: User
    ) -> None:
        with pytest.raises(IntegrityError, match="ck_crop_requests_quantity_positive"):
            create_crop_request(db_session, customer, quantity=0)


class TestListAndCancelCropRequests:
    def test_customer_sees_only_their_own_requests_newest_first(
        self, client: TestClient, db_session: Session, customer: User, other_customer: User
    ) -> None:
        older = create_crop_request(db_session, customer, crop_name="Okra")
        newer = create_crop_request(db_session, customer, crop_name="Collard Greens")
        create_crop_request(db_session, other_customer, crop_name="Okra")

        response = client.get(MY_CROP_REQUESTS_URL, headers=auth_headers(customer))

        assert response.status_code == 200
        assert [request["id"] for request in response.json()] == [newer.id, older.id]

    def test_listing_is_for_customers_only(self, client: TestClient, db_session: Session) -> None:
        farmer = create_user(db_session, role=UserRole.FARMER, email="farmer@example.com")

        assert client.get(MY_CROP_REQUESTS_URL, headers=auth_headers(farmer)).status_code == 403
        assert client.get(MY_CROP_REQUESTS_URL).status_code == 401

    def test_customer_cancels_their_own_request(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        request = create_crop_request(db_session, customer)

        response = client.post(cancel_url(request.id), headers=auth_headers(customer))

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"
        db_session.refresh(request)
        assert request.status is CropRequestStatus.CANCELLED

    def test_cancelling_twice_is_a_conflict(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        request = create_crop_request(db_session, customer)
        client.post(cancel_url(request.id), headers=auth_headers(customer))

        response = client.post(cancel_url(request.id), headers=auth_headers(customer))

        assert response.status_code == 409
        assert response.json() == {"detail": "Only an open crop request can be cancelled"}

    def test_another_customers_request_is_reported_as_not_found(
        self, client: TestClient, db_session: Session, customer: User, other_customer: User
    ) -> None:
        request = create_crop_request(db_session, customer)

        response = client.post(cancel_url(request.id), headers=auth_headers(other_customer))

        assert response.status_code == 404
        db_session.refresh(request)
        assert request.status is CropRequestStatus.OPEN

    def test_farmer_cannot_cancel_a_crop_request(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        farmer = create_user(db_session, role=UserRole.FARMER, email="farmer@example.com")
        request = create_crop_request(db_session, customer)

        response = client.post(cancel_url(request.id), headers=auth_headers(farmer))

        assert response.status_code == 403
        db_session.refresh(request)
        assert request.status is CropRequestStatus.OPEN


class TestCoveredByCommitment:
    def test_request_is_covered_once_the_customer_joins_an_offer_for_that_crop(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        farm = create_farmer_with_farm(db_session, "farmer@example.com")
        create_crop_request(db_session, customer, crop_name="Okra")
        create_crop_request(db_session, customer, crop_name="Collard Greens")
        okra_offer = create_grow_offer(db_session, farm, crop_name="Okra")
        create_commitment(db_session, customer, okra_offer)

        response = client.get(MY_CROP_REQUESTS_URL, headers=auth_headers(customer))

        covered = {request["crop_name"]: request["covered_by_commitment"] for request in response.json()}
        assert covered == {"Okra": True, "Collard Greens": False}

    def test_request_is_uncovered_again_when_the_offer_is_cancelled(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        farm = create_farmer_with_farm(db_session, "farmer@example.com")
        create_crop_request(db_session, customer, crop_name="Okra")
        offer = create_grow_offer(db_session, farm, crop_name="Okra")
        create_commitment(db_session, customer, offer)
        offer.status = GrowOfferStatus.CANCELLED
        db_session.commit()

        response = client.get(MY_CROP_REQUESTS_URL, headers=auth_headers(customer))

        assert response.json()[0]["covered_by_commitment"] is False

    def test_someone_elses_commitment_does_not_cover_the_request(
        self, client: TestClient, db_session: Session, customer: User, other_customer: User
    ) -> None:
        farm = create_farmer_with_farm(db_session, "farmer@example.com")
        create_crop_request(db_session, customer, crop_name="Okra")
        offer = create_grow_offer(db_session, farm, crop_name="Okra")
        create_commitment(db_session, other_customer, offer)

        response = client.get(MY_CROP_REQUESTS_URL, headers=auth_headers(customer))

        assert response.json()[0]["covered_by_commitment"] is False


def test_matching_location_is_the_customers_location_rounded_to_two_decimals(
    db_session: Session, customer: User
) -> None:
    request = create_crop_request(
        db_session, customer, latitude=35.227149, longitude=-80.843127
    )

    longitude, latitude = db_session.execute(
        text(
            "SELECT ST_X(approximate_location::geometry), ST_Y(approximate_location::geometry) "
            "FROM crop_requests WHERE id = :id"
        ),
        {"id": request.id},
    ).one()

    assert (latitude, longitude) == (35.23, -80.84)
