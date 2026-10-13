from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.crop_poll import CropPoll, CropPollStatus
from app.models.farm import Farm
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_crop_poll,
    create_farmer_with_farm,
    create_user,
    create_vote,
)

CROP_POLLS_URL = "/api/crop-polls"
MY_CROP_POLLS_URL = "/api/crop-polls/mine"
SEARCH_URL = "/api/crop-polls/search"

ORIGIN_LATITUDE = 35.2271
ORIGIN_LONGITUDE = -80.8431
MILES_PER_DEGREE_OF_LATITUDE = 68.94


def close_url(poll_id: int) -> str:
    return f"{CROP_POLLS_URL}/{poll_id}/close"


def poll_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"options": ["Okra", "Sweet Corn", "Collard Greens"]}
    return payload | overrides


def count_polls(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(CropPoll)) or 0


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


class TestCreateCropPoll:
    def test_farmer_creates_a_poll_with_the_default_question(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        response = client.post(CROP_POLLS_URL, json=poll_payload(), headers=auth_headers(farmer))

        assert response.status_code == 201
        body = response.json()
        assert body["farm_id"] == farm.id
        assert body["question"] == "What should I grow next?"
        assert body["status"] == "OPEN"
        assert body["total_votes"] == 0
        assert [(option["crop_name"], option["votes"]) for option in body["options"]] == [
            ("Okra", 0),
            ("Sweet Corn", 0),
            ("Collard Greens", 0),
        ]
        assert db_session.get(CropPoll, body["id"]) is not None

    def test_farmer_can_ask_their_own_question(self, client: TestClient, farmer: User) -> None:
        response = client.post(
            CROP_POLLS_URL,
            json=poll_payload(question="  Which greens for fall?  "),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        assert response.json()["question"] == "Which greens for fall?"

    def test_option_names_use_the_same_spelling_as_other_crop_names(
        self, client: TestClient, farmer: User
    ) -> None:
        response = client.post(
            CROP_POLLS_URL,
            json=poll_payload(options=["  okra ", "sweet  CORN"]),
            headers=auth_headers(farmer),
        )

        assert [option["crop_name"] for option in response.json()["options"]] == [
            "Okra",
            "Sweet Corn",
        ]

    def test_farm_and_status_in_the_request_body_are_ignored(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")

        response = client.post(
            CROP_POLLS_URL,
            json=poll_payload(farm_id=other_farm.id, status="CLOSED"),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        assert response.json()["farm_id"] == farm.id
        assert response.json()["status"] == "OPEN"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"options": ["Okra"]},
            {"options": []},
            {"options": [f"Crop {letter}" for letter in "ABCDEFGHI"]},
            {"options": ["okra", " OKRA "]},
            {"options": ["Okra", "  "]},
            {"question": "   "},
            {"question": "Q" * 201},
        ],
        ids=[
            "one option",
            "no options",
            "nine options",
            "same crop twice",
            "blank option",
            "blank question",
            "question too long",
        ],
    )
    def test_invalid_poll_is_rejected(
        self, client: TestClient, db_session: Session, farmer: User, overrides: dict[str, Any]
    ) -> None:
        response = client.post(
            CROP_POLLS_URL, json=poll_payload(**overrides), headers=auth_headers(farmer)
        )

        assert response.status_code == 422
        assert count_polls(db_session) == 0

    def test_farmer_without_a_farm_cannot_create_a_poll(
        self, client: TestClient, db_session: Session
    ) -> None:
        farmer_without_farm = create_user(
            db_session, role=UserRole.FARMER, email="new-farmer@example.com"
        )

        response = client.post(
            CROP_POLLS_URL, json=poll_payload(), headers=auth_headers(farmer_without_farm)
        )

        assert response.status_code == 409
        assert count_polls(db_session) == 0

    def test_only_farmers_can_create_a_poll(
        self, client: TestClient, db_session: Session, farm: Farm, customer: User
    ) -> None:
        assert (
            client.post(CROP_POLLS_URL, json=poll_payload(), headers=auth_headers(customer)).status_code
            == 403
        )
        assert client.post(CROP_POLLS_URL, json=poll_payload()).status_code == 401
        assert count_polls(db_session) == 0


class TestListMyCropPolls:
    def test_farmer_sees_their_own_polls_with_vote_counts(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        create_crop_poll(db_session, other_farm, question="Not mine")
        poll = create_crop_poll(db_session, farm)
        okra, corn, _greens = poll.options
        for number in range(3):
            voter = create_user(
                db_session, role=UserRole.CUSTOMER, email=f"voter-{number}@example.com"
            )
            create_vote(db_session, voter, okra if number < 2 else corn)

        response = client.get(MY_CROP_POLLS_URL, headers=auth_headers(farmer))

        assert response.status_code == 200
        [listed_poll] = response.json()
        assert listed_poll["id"] == poll.id
        assert listed_poll["total_votes"] == 3
        assert {option["crop_name"]: option["votes"] for option in listed_poll["options"]} == {
            "Okra": 2,
            "Sweet Corn": 1,
            "Collard Greens": 0,
        }

    def test_poll_listing_does_not_say_who_voted(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        poll = create_crop_poll(db_session, farm)
        voter = create_user(
            db_session, role=UserRole.CUSTOMER, email="priya@example.com", name="Priya Private"
        )
        create_vote(db_session, voter, poll.options[0])

        response = client.get(MY_CROP_POLLS_URL, headers=auth_headers(farmer))

        assert "Priya" not in response.text
        assert "priya@example.com" not in response.text
        assert "customer_id" not in response.text

    def test_farmer_without_a_farm_has_no_polls(
        self, client: TestClient, db_session: Session
    ) -> None:
        farmer_without_farm = create_user(
            db_session, role=UserRole.FARMER, email="new-farmer@example.com"
        )

        assert client.get(MY_CROP_POLLS_URL, headers=auth_headers(farmer_without_farm)).json() == []

    def test_customer_cannot_list_farmer_polls(self, client: TestClient, customer: User) -> None:
        assert client.get(MY_CROP_POLLS_URL, headers=auth_headers(customer)).status_code == 403


class TestCloseCropPoll:
    def test_farmer_closes_their_own_poll(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        poll = create_crop_poll(db_session, farm)

        response = client.post(close_url(poll.id), headers=auth_headers(farmer))

        assert response.status_code == 200
        assert response.json()["status"] == "CLOSED"
        db_session.refresh(poll)
        assert poll.status is CropPollStatus.CLOSED

    def test_closing_twice_is_a_conflict(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        poll = create_crop_poll(db_session, farm, status=CropPollStatus.CLOSED)

        response = client.post(close_url(poll.id), headers=auth_headers(farmer))

        assert response.status_code == 409
        assert response.json() == {"detail": "This crop poll is already closed"}

    def test_farmer_cannot_close_another_farms_poll(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        other_poll = create_crop_poll(db_session, other_farm)

        response = client.post(close_url(other_poll.id), headers=auth_headers(farmer))

        assert response.status_code == 403
        assert response.json() == {"detail": "You can only manage your own crop polls"}
        db_session.refresh(other_poll)
        assert other_poll.status is CropPollStatus.OPEN

    def test_closing_is_for_farmers_and_existing_polls_only(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm, customer: User
    ) -> None:
        poll = create_crop_poll(db_session, farm)

        assert client.post(close_url(poll.id), headers=auth_headers(customer)).status_code == 403
        assert client.post(close_url(poll.id)).status_code == 401
        assert client.post(close_url(999999), headers=auth_headers(farmer)).status_code == 404


class TestSearchCropPolls:
    def test_only_open_polls_on_farms_within_the_radius_are_returned(
        self, client: TestClient, db_session: Session
    ) -> None:
        near_farm = farm_miles_north(db_session, 3, "Near Farm")
        create_crop_poll(db_session, near_farm, question="Near and open")
        create_crop_poll(
            db_session, near_farm, question="Near but closed", status=CropPollStatus.CLOSED
        )
        create_crop_poll(
            db_session, farm_miles_north(db_session, 20, "Far Farm"), question="Far and open"
        )

        questions_within_5 = [result["poll"]["question"] for result in search(client, radius_miles=5)]
        questions_within_25 = [
            result["poll"]["question"] for result in search(client, radius_miles=25)
        ]

        assert questions_within_5 == ["Near and open"]
        assert sorted(questions_within_25) == ["Far and open", "Near and open"]

    def test_result_reports_the_farm_distance_and_vote_counts(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        poll = create_crop_poll(db_session, farm)
        create_vote(db_session, customer, poll.options[1])

        [result] = search(client, radius_miles=5)

        assert set(result) == {"poll", "farm", "distance_miles"}
        assert result["distance_miles"] == pytest.approx(3, abs=0.05)
        assert result["farm"] == {
            "id": farm.id,
            "farm_name": "Near Farm",
            "city": "Charlotte",
            "state": "NC",
        }
        assert result["poll"]["id"] == poll.id
        assert result["poll"]["total_votes"] == 1
        assert [option["votes"] for option in result["poll"]["options"]] == [0, 1, 0]

    def test_search_needs_no_account(self, client: TestClient, db_session: Session) -> None:
        create_crop_poll(db_session, farm_miles_north(db_session, 3, "Near Farm"))

        response = client.get(
            SEARCH_URL, params={"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE}
        )

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_missing_location_is_rejected(self, client: TestClient) -> None:
        assert client.get(SEARCH_URL, params={"longitude": ORIGIN_LONGITUDE}).status_code == 422
