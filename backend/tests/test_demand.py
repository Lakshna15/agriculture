"""Demand tests place the farm in uptown Charlotte and customers due north of it.

One degree of latitude there spans about 68.94 miles, so a customer's distance
from the farm depends only on latitude and is known in advance.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.crop_request import CropRequestStatus
from app.models.farm import Farm
from app.models.grow_offer import GrowOfferStatus
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_commitment,
    create_crop_request,
    create_farmer_with_farm,
    create_grow_offer,
    create_user,
)

DEMAND_URL = "/api/demand"

FARM_LATITUDE = 35.2271
FARM_LONGITUDE = -80.8431
MILES_PER_DEGREE_OF_LATITUDE = 68.94

DEMAND_FIELDS = {
    "crop_name",
    "unit",
    "customers_interested",
    "estimated_weekly_quantity",
    "one_time_quantity",
}


@pytest.fixture
def farm(db_session: Session) -> Farm:
    return create_farmer_with_farm(
        db_session,
        "farmer@example.com",
        farm_name="Green Acres",
        latitude=FARM_LATITUDE,
        longitude=FARM_LONGITUDE,
    )


@pytest.fixture
def farmer(db_session: Session, farm: Farm) -> User:
    owner = db_session.get(User, farm.owner_id)
    assert owner is not None
    return owner


def customer_number(db_session: Session, number: int) -> User:
    return create_user(
        db_session,
        role=UserRole.CUSTOMER,
        email=f"customer-{number}@example.com",
        name=f"Customer Number {number}",
    )


def request_from(
    db_session: Session, customer: User, *, miles_from_farm: float = 3, **overrides: Any
) -> None:
    """A crop request from a customer the given distance due north of the farm."""
    create_crop_request(
        db_session,
        customer,
        latitude=FARM_LATITUDE + miles_from_farm / MILES_PER_DEGREE_OF_LATITUDE,
        longitude=FARM_LONGITUDE,
        **overrides,
    )


def demand(client: TestClient, farmer: User) -> list[dict[str, Any]]:
    response = client.get(DEMAND_URL, headers=auth_headers(farmer))
    assert response.status_code == 200, response.text
    return response.json()


class TestAggregation:
    def test_requests_for_one_crop_are_added_together(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        request_from(db_session, customer_number(db_session, 1), quantity=2, frequency="WEEKLY")
        request_from(db_session, customer_number(db_session, 2), quantity=4, frequency="WEEKLY")
        request_from(db_session, customer_number(db_session, 3), quantity=13, frequency="MONTHLY")
        request_from(db_session, customer_number(db_session, 4), quantity=10, frequency="ONE_TIME")

        assert demand(client, farmer) == [
            {
                "crop_name": "Okra",
                "unit": "LB",
                "customers_interested": 4,
                # 2 + 4 weekly, plus 13 monthly spread over a year: 13 * 12 / 52 = 3.
                "estimated_weekly_quantity": 9.0,
                "one_time_quantity": 10,
            }
        ]

    def test_crops_and_units_are_reported_separately_most_requested_first(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        for number in (1, 2, 3):
            request_from(db_session, customer_number(db_session, number), crop_name="Okra")
        for number in (4, 5):
            request_from(
                db_session,
                customer_number(db_session, number),
                crop_name="Sweet Corn",
                unit="EACH",
                quantity=6,
            )
        request_from(
            db_session, customer_number(db_session, 6), crop_name="Sweet Corn", unit="DOZEN"
        )

        rows = demand(client, farmer)

        assert [(row["crop_name"], row["unit"], row["customers_interested"]) for row in rows] == [
            ("Okra", "LB", 3),
            ("Sweet Corn", "EACH", 2),
            ("Sweet Corn", "DOZEN", 1),
        ]
        assert rows[1]["estimated_weekly_quantity"] == 12.0

    def test_no_demand_gives_an_empty_list(self, client: TestClient, farmer: User) -> None:
        assert demand(client, farmer) == []


class TestGeographicMatching:
    def test_request_counts_only_when_its_travel_radius_reaches_the_farm(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        request_from(
            db_session,
            customer_number(db_session, 1),
            crop_name="Reaches The Farm",
            miles_from_farm=20,
            radius_miles=25,
        )
        request_from(
            db_session,
            customer_number(db_session, 2),
            crop_name="Stops Short",
            miles_from_farm=20,
            radius_miles=10,
        )

        assert [row["crop_name"] for row in demand(client, farmer)] == ["Reaches The Farm"]

    def test_each_farm_sees_the_demand_around_itself(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        distant_farm = create_farmer_with_farm(
            db_session,
            "distant-farmer@example.com",
            latitude=FARM_LATITUDE + 60 / MILES_PER_DEGREE_OF_LATITUDE,
            longitude=FARM_LONGITUDE,
        )
        distant_farmer = db_session.get(User, distant_farm.owner_id)
        assert distant_farmer is not None
        request_from(db_session, customer_number(db_session, 1), miles_from_farm=3, radius_miles=10)

        assert len(demand(client, farmer)) == 1
        assert demand(client, distant_farmer) == []

    def test_demand_follows_the_farm_when_it_moves(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        request_from(db_session, customer_number(db_session, 1), miles_from_farm=3, radius_miles=10)
        assert len(demand(client, farmer)) == 1

        farm.latitude = FARM_LATITUDE + 60 / MILES_PER_DEGREE_OF_LATITUDE
        db_session.commit()

        assert demand(client, farmer) == []


class TestWhatCountsAsUnmetDemand:
    def test_cancelled_requests_are_not_counted(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        request_from(db_session, customer_number(db_session, 1))
        request_from(db_session, customer_number(db_session, 2), status=CropRequestStatus.CANCELLED)

        [row] = demand(client, farmer)

        assert row["customers_interested"] == 1

    def test_customer_who_joined_an_offer_for_the_crop_is_no_longer_counted(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        joined, waiting = customer_number(db_session, 1), customer_number(db_session, 2)
        request_from(db_session, joined)
        request_from(db_session, waiting)
        request_from(db_session, joined, crop_name="Collard Greens")
        create_commitment(db_session, joined, create_grow_offer(db_session, farm, crop_name="Okra"))

        rows = demand(client, farmer)

        counts = {row["crop_name"]: row["customers_interested"] for row in rows}
        assert counts == {"Okra": 1, "Collard Greens": 1}

    def test_demand_returns_when_the_offer_that_covered_it_is_cancelled(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        customer = customer_number(db_session, 1)
        request_from(db_session, customer)
        offer = create_grow_offer(db_session, farm, crop_name="Okra")
        create_commitment(db_session, customer, offer)
        assert demand(client, farmer) == []

        offer.status = GrowOfferStatus.CANCELLED
        db_session.commit()

        assert demand(client, farmer)[0]["customers_interested"] == 1


class TestPrivacy:
    def test_response_contains_only_aggregate_fields(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        request_from(db_session, customer_number(db_session, 1))

        [row] = demand(client, farmer)

        assert set(row) == DEMAND_FIELDS

    def test_response_reveals_nothing_about_individual_customers(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        customer = create_user(
            db_session,
            role=UserRole.CUSTOMER,
            email="private-person@example.com",
            name="Priya Private",
        )
        customer_latitude = FARM_LATITUDE + 3 / MILES_PER_DEGREE_OF_LATITUDE
        create_crop_request(
            db_session,
            customer,
            latitude=customer_latitude,
            longitude=FARM_LONGITUDE,
            radius_miles=17,
            notes="Leave it at 12 Secret Lane",
        )

        response = client.get(DEMAND_URL, headers=auth_headers(farmer))

        body = response.text
        assert "Priya" not in body
        assert "private-person" not in body
        assert "Secret Lane" not in body
        assert "latitude" not in body
        assert "longitude" not in body
        assert "radius" not in body
        # Neither the exact coordinate nor the rounded one used for matching.
        assert f"{customer_latitude:.4f}" not in body
        assert f"{customer_latitude:.2f}" not in body
        assert "80.84" not in body

    def test_single_request_is_still_reported_as_a_count(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        request_from(db_session, customer_number(db_session, 1), quantity=3)

        assert demand(client, farmer) == [
            {
                "crop_name": "Okra",
                "unit": "LB",
                "customers_interested": 1,
                "estimated_weekly_quantity": 3.0,
                "one_time_quantity": 0,
            }
        ]


class TestAccess:
    def test_customer_cannot_see_demand(self, client: TestClient, db_session: Session) -> None:
        customer = customer_number(db_session, 1)

        assert client.get(DEMAND_URL, headers=auth_headers(customer)).status_code == 403

    def test_unauthenticated_request_is_rejected(self, client: TestClient) -> None:
        assert client.get(DEMAND_URL).status_code == 401

    def test_farmer_without_a_farm_is_asked_to_create_one(
        self, client: TestClient, db_session: Session
    ) -> None:
        farmer_without_farm = create_user(
            db_session, role=UserRole.FARMER, email="new-farmer@example.com"
        )

        response = client.get(DEMAND_URL, headers=auth_headers(farmer_without_farm))

        assert response.status_code == 409
        assert response.json() == {"detail": "Create your farm first"}
