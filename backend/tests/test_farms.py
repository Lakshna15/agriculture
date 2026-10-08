from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.user import User, UserRole
from tests.helpers import auth_headers, create_farm, create_user, farm_payload

FARMS_URL = "/api/farms"
MY_FARM_URL = "/api/farms/me"


def count_farms(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(Farm)) or 0


@pytest.fixture
def farmer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.FARMER, email="farmer@example.com")


@pytest.fixture
def other_farmer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.FARMER, email="other-farmer@example.com")


@pytest.fixture
def customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="customer@example.com")


class TestCreateFarm:
    def test_farmer_creates_a_farm(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        response = client.post(FARMS_URL, json=farm_payload(), headers=auth_headers(farmer))

        assert response.status_code == 201
        body = response.json()
        assert body["owner_id"] == farmer.id
        assert body["farm_name"] == "Green Acres"
        assert body["city"] == "Charlotte"
        assert body["state"] == "NC"
        assert body["latitude"] == 35.2271
        assert body["longitude"] == -80.8431
        assert body["pickup_available"] is True
        assert body["delivery_available"] is False

        stored_farm = db_session.get(Farm, body["id"])
        assert stored_farm is not None
        assert stored_farm.owner_id == farmer.id

    def test_customer_cannot_create_a_farm(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        response = client.post(FARMS_URL, json=farm_payload(), headers=auth_headers(customer))

        assert response.status_code == 403
        assert count_farms(db_session) == 0

    def test_admin_cannot_create_a_farm(self, client: TestClient, db_session: Session) -> None:
        admin = create_user(db_session, role=UserRole.ADMIN, email="admin@example.com")

        response = client.post(FARMS_URL, json=farm_payload(), headers=auth_headers(admin))

        assert response.status_code == 403
        assert count_farms(db_session) == 0

    def test_unauthenticated_request_cannot_create_a_farm(
        self, client: TestClient, db_session: Session
    ) -> None:
        response = client.post(FARMS_URL, json=farm_payload())

        assert response.status_code == 401
        assert count_farms(db_session) == 0

    def test_second_farm_for_the_same_farmer_is_rejected(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        first_response = client.post(FARMS_URL, json=farm_payload(), headers=auth_headers(farmer))
        second_response = client.post(
            FARMS_URL, json=farm_payload(farm_name="Second Farm"), headers=auth_headers(farmer)
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 409
        assert second_response.json() == {"detail": "You already have a farm"}
        assert count_farms(db_session) == 1

    def test_two_farmers_can_each_create_a_farm(
        self, client: TestClient, db_session: Session, farmer: User, other_farmer: User
    ) -> None:
        first_response = client.post(FARMS_URL, json=farm_payload(), headers=auth_headers(farmer))
        second_response = client.post(
            FARMS_URL, json=farm_payload(), headers=auth_headers(other_farmer)
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 201
        assert count_farms(db_session) == 2

    def test_owner_in_the_request_body_is_ignored(
        self, client: TestClient, farmer: User, other_farmer: User
    ) -> None:
        response = client.post(
            FARMS_URL,
            json=farm_payload(owner_id=other_farmer.id, id=999),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        assert response.json()["owner_id"] == farmer.id
        assert response.json()["id"] != 999

    def test_text_fields_are_normalized(self, client: TestClient, farmer: User) -> None:
        response = client.post(
            FARMS_URL,
            json=farm_payload(farm_name="  Green Acres  ", state="nc", description="   ", phone=""),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["farm_name"] == "Green Acres"
        assert body["state"] == "NC"
        assert body["description"] is None
        assert body["phone"] is None


class TestFarmValidation:
    @pytest.mark.parametrize(
        "coordinates",
        [
            {"latitude": 90.0001},
            {"latitude": -90.0001},
            {"longitude": 180.0001},
            {"longitude": -180.0001},
            {"latitude": "north"},
            {"latitude": None},
        ],
        ids=[
            "latitude above 90",
            "latitude below -90",
            "longitude above 180",
            "longitude below -180",
            "latitude not a number",
            "latitude missing",
        ],
    )
    def test_invalid_coordinates_are_rejected(
        self, client: TestClient, db_session: Session, farmer: User, coordinates: dict[str, Any]
    ) -> None:
        response = client.post(
            FARMS_URL, json=farm_payload(**coordinates), headers=auth_headers(farmer)
        )

        assert response.status_code == 422
        assert count_farms(db_session) == 0

    @pytest.mark.parametrize(
        ("latitude", "longitude"),
        [(90, 180), (-90, -180), (0, 0)],
        ids=["north-east limit", "south-west limit", "origin"],
    )
    def test_coordinates_on_the_limits_are_accepted(
        self, client: TestClient, farmer: User, latitude: float, longitude: float
    ) -> None:
        response = client.post(
            FARMS_URL,
            json=farm_payload(latitude=latitude, longitude=longitude),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        assert response.json()["latitude"] == latitude
        assert response.json()["longitude"] == longitude

    @pytest.mark.parametrize(
        "overrides",
        [
            {"farm_name": "   "},
            {"state": "ZZ"},
            {"state": "North Carolina"},
            {"zip_code": "2820"},
            {"zip_code": "28202-12"},
            {"phone": "call me"},
            {"address": ""},
        ],
        ids=[
            "blank name",
            "unknown state code",
            "state not a code",
            "short zip",
            "malformed zip+4",
            "phone with letters",
            "empty address",
        ],
    )
    def test_invalid_fields_are_rejected(
        self, client: TestClient, db_session: Session, farmer: User, overrides: dict[str, Any]
    ) -> None:
        response = client.post(
            FARMS_URL, json=farm_payload(**overrides), headers=auth_headers(farmer)
        )

        assert response.status_code == 422
        assert count_farms(db_session) == 0

    def test_database_rejects_out_of_range_coordinates(
        self, db_session: Session, farmer: User
    ) -> None:
        with pytest.raises(IntegrityError, match="ck_farms_latitude_range"):
            create_farm(db_session, farmer, latitude=91)

    def test_database_rejects_a_second_farm_for_one_owner(
        self, db_session: Session, farmer: User
    ) -> None:
        create_farm(db_session, farmer)

        with pytest.raises(IntegrityError, match="uq_farms_owner_id"):
            create_farm(db_session, farmer, farm_name="Second Farm")


class TestReadFarm:
    def test_farmer_reads_their_own_farm(
        self, client: TestClient, db_session: Session, farmer: User, other_farmer: User
    ) -> None:
        create_farm(db_session, other_farmer, farm_name="Someone Else's Farm")
        farm = create_farm(db_session, farmer)

        response = client.get(MY_FARM_URL, headers=auth_headers(farmer))

        assert response.status_code == 200
        assert response.json()["id"] == farm.id
        assert response.json()["farm_name"] == "Green Acres"

    def test_farmer_without_a_farm_gets_not_found(self, client: TestClient, farmer: User) -> None:
        response = client.get(MY_FARM_URL, headers=auth_headers(farmer))

        assert response.status_code == 404
        assert response.json() == {"detail": "You have not created a farm yet"}

    def test_customer_cannot_use_the_my_farm_endpoint(
        self, client: TestClient, customer: User
    ) -> None:
        response = client.get(MY_FARM_URL, headers=auth_headers(customer))

        assert response.status_code == 403

    def test_my_farm_requires_authentication(self, client: TestClient) -> None:
        response = client.get(MY_FARM_URL)

        assert response.status_code == 401

    def test_anyone_can_read_a_farm_profile(
        self, client: TestClient, db_session: Session, farmer: User, customer: User
    ) -> None:
        farm = create_farm(db_session, farmer)

        anonymous_response = client.get(f"{FARMS_URL}/{farm.id}")
        customer_response = client.get(f"{FARMS_URL}/{farm.id}", headers=auth_headers(customer))

        assert anonymous_response.status_code == 200
        assert anonymous_response.json()["farm_name"] == "Green Acres"
        assert customer_response.status_code == 200

    def test_unknown_farm_is_not_found(self, client: TestClient) -> None:
        response = client.get(f"{FARMS_URL}/999999")

        assert response.status_code == 404
        assert response.json() == {"detail": "Farm not found"}

    @pytest.mark.parametrize("farm_id", ["0", "-1", "99999999999999999999", "abc"])
    def test_malformed_farm_id_is_a_validation_error(
        self, client: TestClient, farm_id: str
    ) -> None:
        response = client.get(f"{FARMS_URL}/{farm_id}")

        assert response.status_code == 422


class TestUpdateFarm:
    def test_farmer_edits_their_own_farm(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        farm = create_farm(db_session, farmer)

        response = client.put(
            f"{FARMS_URL}/{farm.id}",
            json=farm_payload(
                farm_name="Green Acres Organic",
                city="Concord",
                zip_code="28025",
                latitude=35.4088,
                longitude=-80.5795,
                delivery_available=True,
                phone=None,
            ),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == farm.id
        assert body["farm_name"] == "Green Acres Organic"
        assert body["city"] == "Concord"
        assert body["latitude"] == 35.4088
        assert body["delivery_available"] is True
        assert body["phone"] is None

        db_session.refresh(farm)
        assert farm.farm_name == "Green Acres Organic"
        assert farm.owner_id == farmer.id

    def test_farmer_cannot_edit_another_farmers_farm(
        self, client: TestClient, db_session: Session, farmer: User, other_farmer: User
    ) -> None:
        other_farm = create_farm(db_session, other_farmer, farm_name="Neighbor Farm")

        response = client.put(
            f"{FARMS_URL}/{other_farm.id}",
            json=farm_payload(farm_name="Taken Over"),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "You can only edit your own farm"}
        db_session.refresh(other_farm)
        assert other_farm.farm_name == "Neighbor Farm"
        assert other_farm.owner_id == other_farmer.id

    def test_customer_cannot_edit_a_farm(
        self, client: TestClient, db_session: Session, farmer: User, customer: User
    ) -> None:
        farm = create_farm(db_session, farmer)

        response = client.put(
            f"{FARMS_URL}/{farm.id}",
            json=farm_payload(farm_name="Taken Over"),
            headers=auth_headers(customer),
        )

        assert response.status_code == 403
        db_session.refresh(farm)
        assert farm.farm_name == "Green Acres"

    def test_unauthenticated_request_cannot_edit_a_farm(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        farm = create_farm(db_session, farmer)

        response = client.put(f"{FARMS_URL}/{farm.id}", json=farm_payload(farm_name="Taken Over"))

        assert response.status_code == 401

    def test_editing_cannot_transfer_ownership(
        self, client: TestClient, db_session: Session, farmer: User, other_farmer: User
    ) -> None:
        farm = create_farm(db_session, farmer)

        response = client.put(
            f"{FARMS_URL}/{farm.id}",
            json=farm_payload(owner_id=other_farmer.id),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 200
        assert response.json()["owner_id"] == farmer.id
        db_session.refresh(farm)
        assert farm.owner_id == farmer.id

    def test_editing_with_invalid_coordinates_is_rejected(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        farm = create_farm(db_session, farmer)

        response = client.put(
            f"{FARMS_URL}/{farm.id}",
            json=farm_payload(longitude=200),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 422
        db_session.refresh(farm)
        assert farm.longitude == -80.8431

    def test_editing_an_unknown_farm_is_not_found(self, client: TestClient, farmer: User) -> None:
        response = client.put(
            f"{FARMS_URL}/999999", json=farm_payload(), headers=auth_headers(farmer)
        )

        assert response.status_code == 404
