from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.grow_offer import GrowOffer, GrowOfferStatus
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_commitment,
    create_farmer_with_farm,
    create_grow_offer,
    create_user,
    days_from_today,
    grow_offer_payload,
)

GROW_OFFERS_URL = "/api/grow-offers"
MY_GROW_OFFERS_URL = "/api/grow-offers/mine"
SEARCH_URL = "/api/grow-offers/search"

ORIGIN_LATITUDE = 35.2271
ORIGIN_LONGITUDE = -80.8431
MILES_PER_DEGREE_OF_LATITUDE = 68.94


def cancel_url(offer_id: int) -> str:
    return f"{GROW_OFFERS_URL}/{offer_id}/cancel"


def count_offers(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(GrowOffer)) or 0


def farm_miles_north(db_session: Session, miles: float, farm_name: str) -> Farm:
    return create_farmer_with_farm(
        db_session,
        email=f"{farm_name.lower().replace(' ', '-')}@example.com",
        farm_name=farm_name,
        latitude=ORIGIN_LATITUDE + miles / MILES_PER_DEGREE_OF_LATITUDE,
        longitude=ORIGIN_LONGITUDE,
    )


def search(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    query = {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE} | params
    response = client.get(SEARCH_URL, params=query)
    assert response.status_code == 200, response.text
    return response.json()


def crops(results: list[dict[str, Any]]) -> list[str]:
    return [result["offer"]["crop_name"] for result in results]


@pytest.fixture
def farm(db_session: Session) -> Farm:
    return create_farmer_with_farm(db_session, "farmer@example.com", farm_name="Green Acres")


@pytest.fixture
def farmer(db_session: Session, farm: Farm) -> User:
    owner = db_session.get(User, farm.owner_id)
    assert owner is not None
    return owner


@pytest.fixture
def customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="customer@example.com")


class TestCreateGrowOffer:
    def test_farmer_creates_an_open_offer_on_their_farm(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        response = client.post(
            GROW_OFFERS_URL, json=grow_offer_payload(), headers=auth_headers(farmer)
        )

        assert response.status_code == 201
        body = response.json()
        assert body["farm_id"] == farm.id
        assert body["crop_name"] == "Okra"
        assert body["expected_quantity"] == 100
        assert body["unit"] == "LB"
        assert body["estimated_price"] == "3.50"
        assert body["planting_date"] == days_from_today(14).isoformat()
        assert body["expected_harvest_date"] == days_from_today(90).isoformat()
        assert body["minimum_customers"] == 3
        assert body["status"] == "OPEN"
        assert body["committed_customers"] == 0
        assert body["committed_quantity"] == 0
        assert db_session.get(GrowOffer, body["id"]) is not None

    def test_crop_name_uses_the_same_spelling_as_crop_requests(
        self, client: TestClient, farmer: User
    ) -> None:
        response = client.post(
            GROW_OFFERS_URL,
            json=grow_offer_payload(crop_name="  sweet  CORN "),
            headers=auth_headers(farmer),
        )

        assert response.json()["crop_name"] == "Sweet Corn"

    def test_crop_already_planted_can_still_be_offered(
        self, client: TestClient, farmer: User
    ) -> None:
        response = client.post(
            GROW_OFFERS_URL,
            json=grow_offer_payload(planting_date=days_from_today(-20).isoformat()),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201

    def test_farm_and_status_in_the_request_body_are_ignored(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")

        response = client.post(
            GROW_OFFERS_URL,
            json=grow_offer_payload(farm_id=other_farm.id, status="CONFIRMED"),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        assert response.json()["farm_id"] == farm.id
        assert response.json()["status"] == "OPEN"

    def test_farmer_without_a_farm_cannot_create_an_offer(
        self, client: TestClient, db_session: Session
    ) -> None:
        farmer_without_farm = create_user(
            db_session, role=UserRole.FARMER, email="new-farmer@example.com"
        )

        response = client.post(
            GROW_OFFERS_URL, json=grow_offer_payload(), headers=auth_headers(farmer_without_farm)
        )

        assert response.status_code == 409
        assert count_offers(db_session) == 0

    def test_customer_cannot_create_an_offer(
        self, client: TestClient, db_session: Session, farm: Farm, customer: User
    ) -> None:
        response = client.post(
            GROW_OFFERS_URL, json=grow_offer_payload(), headers=auth_headers(customer)
        )

        assert response.status_code == 403
        assert count_offers(db_session) == 0

    def test_unauthenticated_request_cannot_create_an_offer(
        self, client: TestClient, db_session: Session, farm: Farm
    ) -> None:
        response = client.post(GROW_OFFERS_URL, json=grow_offer_payload())

        assert response.status_code == 401
        assert count_offers(db_session) == 0

    def test_harvest_date_in_the_past_is_rejected(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        response = client.post(
            GROW_OFFERS_URL,
            json=grow_offer_payload(
                planting_date=days_from_today(-60).isoformat(),
                expected_harvest_date=days_from_today(-1).isoformat(),
            ),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 422
        assert response.json() == {"detail": "Expected harvest date cannot be in the past"}
        assert count_offers(db_session) == 0

    @pytest.mark.parametrize(
        "overrides",
        [
            {"crop_name": " "},
            {"expected_quantity": 0},
            {"expected_quantity": 2.5},
            {"unit": "BARREL"},
            {"estimated_price": "0"},
            {"estimated_price": "3.555"},
            {"minimum_customers": 0},
            {"minimum_customers": -2},
            {
                "planting_date": days_from_today(90).isoformat(),
                "expected_harvest_date": days_from_today(14).isoformat(),
            },
            {"planting_date": "soon"},
        ],
        ids=[
            "blank crop",
            "zero quantity",
            "fractional quantity",
            "unknown unit",
            "zero price",
            "fractional cents",
            "zero minimum customers",
            "negative minimum customers",
            "harvest before planting",
            "malformed date",
        ],
    )
    def test_invalid_offer_is_rejected(
        self, client: TestClient, db_session: Session, farmer: User, overrides: dict[str, Any]
    ) -> None:
        response = client.post(
            GROW_OFFERS_URL, json=grow_offer_payload(**overrides), headers=auth_headers(farmer)
        )

        assert response.status_code == 422
        assert count_offers(db_session) == 0

    def test_database_rejects_an_offer_that_needs_no_customers(
        self, db_session: Session, farm: Farm
    ) -> None:
        with pytest.raises(IntegrityError, match="ck_grow_offers_minimum_customers_positive"):
            create_grow_offer(db_session, farm, minimum_customers=0)


class TestListMyGrowOffers:
    def test_farmer_sees_their_own_offers_with_commitment_progress(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm, customer: User
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        create_grow_offer(db_session, other_farm, crop_name="Neighbor's Kale")
        okra = create_grow_offer(db_session, farm, crop_name="Okra", minimum_customers=20)
        corn = create_grow_offer(db_session, farm, crop_name="Sweet Corn")
        second_customer = create_user(
            db_session, role=UserRole.CUSTOMER, email="second-customer@example.com"
        )
        create_commitment(db_session, customer, okra, quantity=5)
        create_commitment(db_session, second_customer, okra, quantity=7)

        response = client.get(MY_GROW_OFFERS_URL, headers=auth_headers(farmer))

        assert response.status_code == 200
        offers = {offer["crop_name"]: offer for offer in response.json()}
        assert set(offers) == {"Okra", "Sweet Corn"}
        assert offers["Okra"]["id"] == okra.id
        assert offers["Okra"]["committed_customers"] == 2
        assert offers["Okra"]["minimum_customers"] == 20
        assert offers["Okra"]["committed_quantity"] == 12
        assert offers["Sweet Corn"]["id"] == corn.id
        assert offers["Sweet Corn"]["committed_customers"] == 0

    def test_offer_listing_names_no_customers(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        named_customer = create_user(
            db_session, role=UserRole.CUSTOMER, email="priya@example.com", name="Priya Private"
        )
        create_commitment(db_session, named_customer, create_grow_offer(db_session, farm))

        response = client.get(MY_GROW_OFFERS_URL, headers=auth_headers(farmer))

        assert "Priya" not in response.text
        assert "priya@example.com" not in response.text
        assert "customer_id" not in response.text

    def test_farmer_without_a_farm_has_no_offers(
        self, client: TestClient, db_session: Session
    ) -> None:
        farmer_without_farm = create_user(
            db_session, role=UserRole.FARMER, email="new-farmer@example.com"
        )

        response = client.get(MY_GROW_OFFERS_URL, headers=auth_headers(farmer_without_farm))

        assert response.json() == []

    def test_customer_cannot_list_farmer_offers(self, client: TestClient, customer: User) -> None:
        assert client.get(MY_GROW_OFFERS_URL, headers=auth_headers(customer)).status_code == 403


class TestSearchGrowOffers:
    def test_only_offers_on_farms_within_the_radius_are_returned(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_grow_offer(db_session, farm_miles_north(db_session, 3, "Near Farm"), crop_name="Okra")
        create_grow_offer(db_session, farm_miles_north(db_session, 20, "Far Farm"), crop_name="Kale")
        create_grow_offer(
            db_session, farm_miles_north(db_session, 40, "Distant Farm"), crop_name="Leeks"
        )

        assert crops(search(client, radius_miles=5)) == ["Okra"]
        assert sorted(crops(search(client, radius_miles=25))) == ["Kale", "Okra"]

    def test_result_reports_the_farm_distance_and_progress(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        offer = create_grow_offer(db_session, farm, minimum_customers=20)
        create_commitment(db_session, customer, offer, quantity=8)

        [result] = search(client, radius_miles=5)

        assert set(result) == {"offer", "farm", "distance_miles"}
        assert result["distance_miles"] == pytest.approx(3, abs=0.05)
        assert result["farm"] == {
            "id": farm.id,
            "farm_name": "Near Farm",
            "city": "Charlotte",
            "state": "NC",
        }
        assert result["offer"]["id"] == offer.id
        assert result["offer"]["committed_customers"] == 1
        assert result["offer"]["minimum_customers"] == 20
        assert result["offer"]["committed_quantity"] == 8
        assert result["offer"]["expected_quantity"] == 100

    def test_only_offers_that_can_still_be_joined_are_returned(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        for status in GrowOfferStatus:
            create_grow_offer(
                db_session, farm, crop_name=f"Crop {status.value.title()}", status=status
            )

        assert sorted(crops(search(client, radius_miles=5))) == ["Crop Confirmed", "Crop Open"]

    def test_offers_whose_harvest_date_has_passed_are_not_returned(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        create_grow_offer(
            db_session,
            farm,
            crop_name="Stale",
            planting_date=days_from_today(-90),
            expected_harvest_date=days_from_today(-1),
        )
        create_grow_offer(db_session, farm, crop_name="Current")

        assert crops(search(client, radius_miles=5)) == ["Current"]

    def test_results_are_ordered_by_soonest_harvest(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        create_grow_offer(db_session, farm, crop_name="Later", expected_harvest_date=days_from_today(120))
        create_grow_offer(db_session, farm, crop_name="Sooner", expected_harvest_date=days_from_today(40))

        assert crops(search(client, radius_miles=5)) == ["Sooner", "Later"]

    def test_crop_filter_matches_part_of_the_name_ignoring_case(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        create_grow_offer(db_session, farm, crop_name="Sweet Corn")
        create_grow_offer(db_session, farm, crop_name="Okra")

        assert crops(search(client, radius_miles=5, crop="CORN")) == ["Sweet Corn"]
        assert search(client, radius_miles=5, crop="%") == []

    def test_search_needs_no_account(self, client: TestClient, db_session: Session) -> None:
        create_grow_offer(db_session, farm_miles_north(db_session, 3, "Near Farm"))

        response = client.get(
            SEARCH_URL, params={"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE}
        )

        assert response.status_code == 200
        assert len(response.json()) == 1

    @pytest.mark.parametrize(
        "params",
        [
            {"longitude": ORIGIN_LONGITUDE},
            {"latitude": 91, "longitude": ORIGIN_LONGITUDE},
            {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE, "radius_miles": 0},
        ],
        ids=["missing latitude", "latitude out of range", "zero radius"],
    )
    def test_invalid_parameters_are_rejected(
        self, client: TestClient, params: dict[str, Any]
    ) -> None:
        assert client.get(SEARCH_URL, params=params).status_code == 422


class TestCancelGrowOffer:
    @pytest.mark.parametrize("status", [GrowOfferStatus.OPEN, GrowOfferStatus.CONFIRMED])
    def test_farmer_cancels_an_offer_that_has_not_started_growing(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        farm: Farm,
        status: GrowOfferStatus,
    ) -> None:
        offer = create_grow_offer(db_session, farm, status=status)

        response = client.post(cancel_url(offer.id), headers=auth_headers(farmer))

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"
        db_session.refresh(offer)
        assert offer.status is GrowOfferStatus.CANCELLED

    @pytest.mark.parametrize(
        "status",
        [
            GrowOfferStatus.GROWING,
            GrowOfferStatus.READY,
            GrowOfferStatus.COMPLETED,
            GrowOfferStatus.CANCELLED,
        ],
    )
    def test_offer_past_confirmation_cannot_be_cancelled(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        farm: Farm,
        status: GrowOfferStatus,
    ) -> None:
        offer = create_grow_offer(db_session, farm, status=status)

        response = client.post(cancel_url(offer.id), headers=auth_headers(farmer))

        assert response.status_code == 409
        assert response.json() == {
            "detail": "Only an open or confirmed grow offer can be cancelled"
        }
        db_session.refresh(offer)
        assert offer.status is status

    def test_farmer_cannot_cancel_another_farms_offer(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        other_offer = create_grow_offer(db_session, other_farm)

        response = client.post(cancel_url(other_offer.id), headers=auth_headers(farmer))

        assert response.status_code == 403
        assert response.json() == {"detail": "You can only manage your own grow offers"}
        db_session.refresh(other_offer)
        assert other_offer.status is GrowOfferStatus.OPEN

    def test_customer_cannot_cancel_an_offer(
        self, client: TestClient, db_session: Session, farm: Farm, customer: User
    ) -> None:
        offer = create_grow_offer(db_session, farm)

        assert client.post(cancel_url(offer.id), headers=auth_headers(customer)).status_code == 403
        assert client.post(cancel_url(offer.id)).status_code == 401

    def test_cancelling_an_unknown_offer_is_not_found(
        self, client: TestClient, farmer: User, farm: Farm
    ) -> None:
        assert client.post(cancel_url(999999), headers=auth_headers(farmer)).status_code == 404
