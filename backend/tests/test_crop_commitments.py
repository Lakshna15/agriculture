import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.grow_offer import CropCommitment, GrowOffer, GrowOfferStatus
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_commitment,
    create_farmer_with_farm,
    create_grow_offer,
    create_user,
)

COMMITMENTS_URL = "/api/crop-commitments"
MY_COMMITMENTS_URL = "/api/crop-commitments/mine"


def count_commitments(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(CropCommitment)) or 0


def commit(client: TestClient, customer: User, offer: GrowOffer, quantity: int = 5):
    return client.post(
        COMMITMENTS_URL,
        json={"grow_offer_id": offer.id, "quantity": quantity},
        headers=auth_headers(customer),
    )


@pytest.fixture
def farm(db_session: Session) -> Farm:
    return create_farmer_with_farm(db_session, "farmer@example.com", farm_name="Green Acres")


@pytest.fixture
def farmer(db_session: Session, farm: Farm) -> User:
    owner = db_session.get(User, farm.owner_id)
    assert owner is not None
    return owner


@pytest.fixture
def offer(db_session: Session, farm: Farm) -> GrowOffer:
    return create_grow_offer(db_session, farm, expected_quantity=100, minimum_customers=3)


@pytest.fixture
def customers(db_session: Session) -> list[User]:
    """Five customers, enough to pass a threshold of three with room to spare."""
    return [
        create_user(db_session, role=UserRole.CUSTOMER, email=f"customer-{number}@example.com")
        for number in range(1, 6)
    ]


class TestJoinGrowOffer:
    def test_customer_commits_to_an_offer(
        self,
        client: TestClient,
        db_session: Session,
        customers: list[User],
        offer: GrowOffer,
        farm: Farm,
    ) -> None:
        response = commit(client, customers[0], offer, quantity=8)

        assert response.status_code == 201
        body = response.json()
        assert body["quantity"] == 8
        assert body["offer"]["id"] == offer.id
        assert body["offer"]["crop_name"] == "Okra"
        assert body["offer"]["status"] == "OPEN"
        assert body["offer"]["committed_customers"] == 1
        assert body["offer"]["committed_quantity"] == 8
        assert body["farm"] == {
            "id": farm.id,
            "farm_name": "Green Acres",
            "city": "Charlotte",
            "state": "NC",
        }

        stored_commitment = db_session.get(CropCommitment, body["id"])
        assert stored_commitment is not None
        assert stored_commitment.customer_id == customers[0].id

    def test_customer_can_commit_only_once_to_an_offer(
        self, client: TestClient, db_session: Session, customers: list[User], offer: GrowOffer
    ) -> None:
        first = commit(client, customers[0], offer, quantity=5)
        second = commit(client, customers[0], offer, quantity=9)

        assert first.status_code == 201
        assert second.status_code == 409
        assert second.json() == {"detail": "You have already committed to this grow offer"}
        assert count_commitments(db_session) == 1

    def test_customer_can_commit_to_several_offers(
        self, client: TestClient, db_session: Session, customers: list[User], farm: Farm
    ) -> None:
        okra = create_grow_offer(db_session, farm, crop_name="Okra")
        corn = create_grow_offer(db_session, farm, crop_name="Sweet Corn")

        assert commit(client, customers[0], okra).status_code == 201
        assert commit(client, customers[0], corn).status_code == 201

    def test_database_rejects_a_second_commitment_from_the_same_customer(
        self, db_session: Session, customers: list[User], offer: GrowOffer
    ) -> None:
        create_commitment(db_session, customers[0], offer)

        with pytest.raises(IntegrityError, match="uq_crop_commitments_grow_offer_id_customer_id"):
            create_commitment(db_session, customers[0], offer)

    def test_customer_in_the_request_body_is_ignored(
        self, client: TestClient, db_session: Session, customers: list[User], offer: GrowOffer
    ) -> None:
        response = client.post(
            COMMITMENTS_URL,
            json={"grow_offer_id": offer.id, "quantity": 5, "customer_id": customers[1].id},
            headers=auth_headers(customers[0]),
        )

        assert response.status_code == 201
        stored_commitment = db_session.get(CropCommitment, response.json()["id"])
        assert stored_commitment is not None
        assert stored_commitment.customer_id == customers[0].id

    @pytest.mark.parametrize("quantity", [0, -4, 1.5, "five", None])
    def test_invalid_quantity_is_rejected(
        self,
        client: TestClient,
        db_session: Session,
        customers: list[User],
        offer: GrowOffer,
        quantity: object,
    ) -> None:
        response = client.post(
            COMMITMENTS_URL,
            json={"grow_offer_id": offer.id, "quantity": quantity},
            headers=auth_headers(customers[0]),
        )

        assert response.status_code == 422
        assert count_commitments(db_session) == 0

    def test_farmer_cannot_commit_to_an_offer(
        self, client: TestClient, db_session: Session, farmer: User, offer: GrowOffer
    ) -> None:
        response = commit(client, farmer, offer)

        assert response.status_code == 403
        assert count_commitments(db_session) == 0

    def test_unauthenticated_request_cannot_commit(
        self, client: TestClient, db_session: Session, offer: GrowOffer
    ) -> None:
        response = client.post(COMMITMENTS_URL, json={"grow_offer_id": offer.id, "quantity": 5})

        assert response.status_code == 401
        assert count_commitments(db_session) == 0

    def test_unknown_offer_is_not_found(self, client: TestClient, customers: list[User]) -> None:
        response = client.post(
            COMMITMENTS_URL,
            json={"grow_offer_id": 999999, "quantity": 5},
            headers=auth_headers(customers[0]),
        )

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "status",
        [
            GrowOfferStatus.GROWING,
            GrowOfferStatus.READY,
            GrowOfferStatus.COMPLETED,
            GrowOfferStatus.CANCELLED,
        ],
    )
    def test_offer_that_is_no_longer_accepting_commitments_cannot_be_joined(
        self,
        client: TestClient,
        db_session: Session,
        customers: list[User],
        farm: Farm,
        status: GrowOfferStatus,
    ) -> None:
        closed_offer = create_grow_offer(db_session, farm, status=status)

        response = commit(client, customers[0], closed_offer)

        assert response.status_code == 409
        assert response.json() == {"detail": "This grow offer is no longer accepting commitments"}
        assert count_commitments(db_session) == 0


class TestCommittedQuantity:
    def test_commitments_cannot_add_up_to_more_than_the_expected_harvest(
        self, client: TestClient, db_session: Session, customers: list[User], farm: Farm
    ) -> None:
        small_offer = create_grow_offer(db_session, farm, expected_quantity=10)

        first = commit(client, customers[0], small_offer, quantity=7)
        too_much = commit(client, customers[1], small_offer, quantity=4)
        exactly_the_rest = commit(client, customers[1], small_offer, quantity=3)
        nothing_left = commit(client, customers[2], small_offer, quantity=1)

        assert first.status_code == 201
        assert too_much.status_code == 409
        assert too_much.json() == {"detail": "Only 3 left in this grow offer"}
        assert exactly_the_rest.status_code == 201
        assert nothing_left.status_code == 409
        assert nothing_left.json() == {"detail": "This grow offer is fully committed"}
        assert count_commitments(db_session) == 2


class TestConfirmationThreshold:
    def test_offer_stays_open_until_enough_customers_have_committed(
        self, client: TestClient, db_session: Session, customers: list[User], offer: GrowOffer
    ) -> None:
        first = commit(client, customers[0], offer)
        second = commit(client, customers[1], offer)

        assert first.json()["offer"]["status"] == "OPEN"
        assert second.json()["offer"]["status"] == "OPEN"
        assert second.json()["offer"]["committed_customers"] == 2
        db_session.refresh(offer)
        assert offer.status is GrowOfferStatus.OPEN

    def test_the_commitment_that_reaches_the_threshold_confirms_the_offer(
        self, client: TestClient, db_session: Session, customers: list[User], offer: GrowOffer
    ) -> None:
        commit(client, customers[0], offer)
        commit(client, customers[1], offer)

        third = commit(client, customers[2], offer)

        assert third.status_code == 201
        assert third.json()["offer"]["status"] == "CONFIRMED"
        assert third.json()["offer"]["committed_customers"] == 3
        db_session.refresh(offer)
        assert offer.status is GrowOfferStatus.CONFIRMED

    def test_confirmed_offer_keeps_accepting_commitments_and_stays_confirmed(
        self, client: TestClient, db_session: Session, customers: list[User], offer: GrowOffer
    ) -> None:
        for customer in customers[:3]:
            commit(client, customer, offer)

        fourth = commit(client, customers[3], offer)

        assert fourth.status_code == 201
        assert fourth.json()["offer"]["status"] == "CONFIRMED"
        assert fourth.json()["offer"]["committed_customers"] == 4

    def test_threshold_of_one_is_met_by_the_first_commitment(
        self, client: TestClient, db_session: Session, customers: list[User], farm: Farm
    ) -> None:
        single_customer_offer = create_grow_offer(db_session, farm, minimum_customers=1)

        response = commit(client, customers[0], single_customer_offer)

        assert response.json()["offer"]["status"] == "CONFIRMED"

    def test_threshold_counts_customers_not_quantity(
        self, client: TestClient, db_session: Session, customers: list[User], offer: GrowOffer
    ) -> None:
        response = commit(client, customers[0], offer, quantity=100)

        assert response.status_code == 201
        assert response.json()["offer"]["committed_quantity"] == 100
        assert response.json()["offer"]["status"] == "OPEN"

    def test_a_refused_commitment_does_not_confirm_the_offer(
        self, client: TestClient, db_session: Session, customers: list[User], farm: Farm
    ) -> None:
        tight_offer = create_grow_offer(
            db_session, farm, expected_quantity=10, minimum_customers=3
        )
        commit(client, customers[0], tight_offer, quantity=5)
        commit(client, customers[1], tight_offer, quantity=5)

        refused = commit(client, customers[2], tight_offer, quantity=1)

        assert refused.status_code == 409
        db_session.refresh(tight_offer)
        assert tight_offer.status is GrowOfferStatus.OPEN


class TestListMyCommitments:
    def test_customer_sees_their_own_commitments_with_current_progress(
        self, client: TestClient, db_session: Session, customers: list[User], offer: GrowOffer
    ) -> None:
        own = create_commitment(db_session, customers[0], offer, quantity=6)
        create_commitment(db_session, customers[1], offer, quantity=4)

        response = client.get(MY_COMMITMENTS_URL, headers=auth_headers(customers[0]))

        assert response.status_code == 200
        [commitment] = response.json()
        assert commitment["id"] == own.id
        assert commitment["quantity"] == 6
        assert commitment["offer"]["crop_name"] == "Okra"
        assert commitment["offer"]["committed_customers"] == 2
        assert commitment["offer"]["minimum_customers"] == 3
        assert commitment["offer"]["committed_quantity"] == 10
        assert commitment["farm"]["farm_name"] == "Green Acres"

    def test_customer_with_no_commitments_gets_an_empty_list(
        self, client: TestClient, customers: list[User]
    ) -> None:
        response = client.get(MY_COMMITMENTS_URL, headers=auth_headers(customers[0]))

        assert response.json() == []

    def test_listing_is_for_customers_only(self, client: TestClient, farmer: User) -> None:
        assert client.get(MY_COMMITMENTS_URL, headers=auth_headers(farmer)).status_code == 403
        assert client.get(MY_COMMITMENTS_URL).status_code == 401
