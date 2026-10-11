from datetime import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.event import FarmEvent
from app.models.farm import Farm
from app.models.reservation import ReservationStatus
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_event,
    create_event_reservation,
    create_farmer_with_farm,
    create_user,
    days_from_today,
    event_payload,
)

EVENTS_URL = "/api/events"
MY_EVENTS_URL = "/api/events/mine"
SEARCH_URL = "/api/events/search"

ORIGIN_LATITUDE = 35.2271
ORIGIN_LONGITUDE = -80.8431
MILES_PER_DEGREE_OF_LATITUDE = 68.94


def count_events(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(FarmEvent)) or 0


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


def event_titles(results: list[dict[str, Any]]) -> list[str]:
    return [result["event"]["title"] for result in results]


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


class TestCreateEvent:
    def test_farmer_creates_an_event_on_their_farm(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        response = client.post(EVENTS_URL, json=event_payload(), headers=auth_headers(farmer))

        assert response.status_code == 201
        body = response.json()
        assert body["farm_id"] == farm.id
        assert body["title"] == "Strawberry Picking Morning"
        assert body["event_type"] == "STRAWBERRY_PICKING"
        assert body["event_date"] == days_from_today(7).isoformat()
        assert body["start_time"] == "09:00:00"
        assert body["end_time"] == "12:00:00"
        assert body["price"] == "12.00"
        assert body["capacity"] == 20
        assert body["spots_remaining"] == 20
        assert db_session.get(FarmEvent, body["id"]) is not None

    def test_free_event_is_allowed(self, client: TestClient, farmer: User) -> None:
        response = client.post(
            EVENTS_URL, json=event_payload(price="0"), headers=auth_headers(farmer)
        )

        assert response.status_code == 201
        assert response.json()["price"] == "0.00"

    def test_event_today_is_allowed(self, client: TestClient, farmer: User) -> None:
        response = client.post(
            EVENTS_URL,
            json=event_payload(event_date=days_from_today(0).isoformat()),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201

    def test_farm_in_the_request_body_is_ignored(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")

        response = client.post(
            EVENTS_URL, json=event_payload(farm_id=other_farm.id), headers=auth_headers(farmer)
        )

        assert response.status_code == 201
        assert response.json()["farm_id"] == farm.id

    def test_farmer_without_a_farm_cannot_create_an_event(
        self, client: TestClient, db_session: Session
    ) -> None:
        farmer_without_farm = create_user(
            db_session, role=UserRole.FARMER, email="new-farmer@example.com"
        )

        response = client.post(
            EVENTS_URL, json=event_payload(), headers=auth_headers(farmer_without_farm)
        )

        assert response.status_code == 409
        assert response.json() == {"detail": "Create your farm first"}
        assert count_events(db_session) == 0

    def test_customer_cannot_create_an_event(
        self, client: TestClient, db_session: Session, farm: Farm, customer: User
    ) -> None:
        response = client.post(EVENTS_URL, json=event_payload(), headers=auth_headers(customer))

        assert response.status_code == 403
        assert count_events(db_session) == 0

    def test_unauthenticated_request_cannot_create_an_event(
        self, client: TestClient, db_session: Session, farm: Farm
    ) -> None:
        response = client.post(EVENTS_URL, json=event_payload())

        assert response.status_code == 401
        assert count_events(db_session) == 0

    def test_event_in_the_past_is_rejected(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        response = client.post(
            EVENTS_URL,
            json=event_payload(event_date=days_from_today(-1).isoformat()),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 422
        assert response.json() == {"detail": "Event date cannot be in the past"}
        assert count_events(db_session) == 0

    @pytest.mark.parametrize(
        "overrides",
        [
            {"title": "  "},
            {"event_type": "ROCK_CONCERT"},
            {"start_time": "12:00:00", "end_time": "09:00:00"},
            {"start_time": "09:00:00", "end_time": "09:00:00"},
            {"price": "-1.00"},
            {"price": "5.555"},
            {"capacity": 0},
            {"capacity": -5},
            {"capacity": 2.5},
            {"event_date": "next week"},
        ],
        ids=[
            "blank title",
            "unknown type",
            "ends before it starts",
            "zero length",
            "negative price",
            "fractional cents",
            "zero capacity",
            "negative capacity",
            "fractional capacity",
            "malformed date",
        ],
    )
    def test_invalid_event_is_rejected(
        self, client: TestClient, db_session: Session, farmer: User, overrides: dict[str, Any]
    ) -> None:
        response = client.post(
            EVENTS_URL, json=event_payload(**overrides), headers=auth_headers(farmer)
        )

        assert response.status_code == 422
        assert count_events(db_session) == 0

    def test_database_rejects_an_event_with_no_capacity(
        self, db_session: Session, farm: Farm
    ) -> None:
        with pytest.raises(IntegrityError, match="ck_farm_events_capacity_positive"):
            create_event(db_session, farm, capacity=0)

    def test_database_rejects_an_event_that_ends_before_it_starts(
        self, db_session: Session, farm: Farm
    ) -> None:
        with pytest.raises(IntegrityError, match="ck_farm_events_ends_after_it_starts"):
            create_event(db_session, farm, start_time=time(12, 0), end_time=time(9, 0))


class TestListMyEvents:
    def test_farmer_sees_their_own_events_soonest_first_with_spots_remaining(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm, customer: User
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        create_event(db_session, other_farm, title="Neighbor's Tour")
        later = create_event(db_session, farm, title="Later Event", event_date=days_from_today(14))
        sooner = create_event(db_session, farm, title="Sooner Event", capacity=10)
        create_event_reservation(db_session, customer, sooner, party_size=4)
        create_event_reservation(
            db_session, customer, sooner, party_size=3, status=ReservationStatus.CANCELLED
        )

        response = client.get(MY_EVENTS_URL, headers=auth_headers(farmer))

        assert response.status_code == 200
        assert [event["id"] for event in response.json()] == [sooner.id, later.id]
        assert response.json()[0]["spots_remaining"] == 6
        assert response.json()[1]["spots_remaining"] == 20

    def test_farmer_without_a_farm_has_no_events(
        self, client: TestClient, db_session: Session
    ) -> None:
        farmer_without_farm = create_user(
            db_session, role=UserRole.FARMER, email="new-farmer@example.com"
        )

        response = client.get(MY_EVENTS_URL, headers=auth_headers(farmer_without_farm))

        assert response.json() == []

    def test_customer_cannot_list_farmer_events(self, client: TestClient, customer: User) -> None:
        assert client.get(MY_EVENTS_URL, headers=auth_headers(customer)).status_code == 403


class TestSearchEvents:
    def test_only_events_on_farms_within_the_radius_are_returned(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_event(db_session, farm_miles_north(db_session, 3, "Near Farm"), title="Near Event")
        create_event(db_session, farm_miles_north(db_session, 20, "Far Farm"), title="Far Event")
        create_event(
            db_session, farm_miles_north(db_session, 40, "Distant Farm"), title="Distant Event"
        )

        assert event_titles(search(client, radius_miles=5)) == ["Near Event"]
        assert sorted(event_titles(search(client, radius_miles=25))) == ["Far Event", "Near Event"]

    def test_result_reports_distance_farm_and_spots_remaining(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        event = create_event(db_session, farm, capacity=10)
        create_event_reservation(db_session, customer, event, party_size=4)

        [result] = search(client, radius_miles=5)

        assert set(result) == {"event", "farm", "distance_miles"}
        assert result["distance_miles"] == pytest.approx(3, abs=0.05)
        assert result["farm"] == {
            "id": farm.id,
            "farm_name": "Near Farm",
            "city": "Charlotte",
            "state": "NC",
        }
        assert result["event"]["id"] == event.id
        assert result["event"]["capacity"] == 10
        assert result["event"]["spots_remaining"] == 6
        assert result["event"]["price"] == "12.00"

    def test_past_events_are_not_returned_but_todays_are(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        create_event(db_session, farm, title="Yesterday", event_date=days_from_today(-1))
        create_event(db_session, farm, title="Today", event_date=days_from_today(0))
        create_event(db_session, farm, title="Next Week", event_date=days_from_today(7))

        assert event_titles(search(client, radius_miles=5)) == ["Today", "Next Week"]

    def test_results_are_ordered_by_date_and_start_time(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        day = days_from_today(5)
        create_event(db_session, farm, title="Afternoon", event_date=day, start_time=time(14, 0), end_time=time(16, 0))
        create_event(db_session, farm, title="Day After", event_date=days_from_today(6))
        create_event(db_session, farm, title="Morning", event_date=day, start_time=time(9, 0), end_time=time(11, 0))

        assert event_titles(search(client, radius_miles=5)) == ["Morning", "Afternoon", "Day After"]

    def test_event_type_filter(self, client: TestClient, db_session: Session) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        create_event(db_session, farm, title="Berries", event_type="STRAWBERRY_PICKING")
        create_event(db_session, farm, title="Tour", event_type="FARM_TOUR")

        assert event_titles(search(client, radius_miles=5, event_type="FARM_TOUR")) == ["Tour"]

    def test_fully_booked_event_is_still_listed_with_no_spots(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        event = create_event(db_session, farm_miles_north(db_session, 3, "Near Farm"), capacity=4)
        create_event_reservation(db_session, customer, event, party_size=4)

        [result] = search(client, radius_miles=5)

        assert result["event"]["spots_remaining"] == 0

    def test_search_needs_no_account(self, client: TestClient, db_session: Session) -> None:
        create_event(db_session, farm_miles_north(db_session, 3, "Near Farm"))

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
            {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE, "event_type": "CONCERT"},
        ],
        ids=["missing latitude", "latitude out of range", "zero radius", "unknown type"],
    )
    def test_invalid_parameters_are_rejected(
        self, client: TestClient, params: dict[str, Any]
    ) -> None:
        assert client.get(SEARCH_URL, params=params).status_code == 422
