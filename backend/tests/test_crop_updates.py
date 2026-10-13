from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.crop_update import CropStage, CropUpdate
from app.models.farm import Farm
from app.models.grow_offer import GrowOffer, GrowOfferStatus
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_commitment,
    create_crop_update,
    create_farmer_with_farm,
    create_grow_offer,
    create_user,
)

GROW_OFFERS_URL = "/api/grow-offers"


def updates_url(offer: GrowOffer) -> str:
    return f"{GROW_OFFERS_URL}/{offer.id}/updates"


def update_payload(**overrides: Any) -> dict[str, Any]:
    payload = {"stage": "PLANTED", "message": "Seedlings went into the ground today."}
    return payload | overrides


def count_updates(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(CropUpdate)) or 0


@pytest.fixture
def farm(db_session: Session) -> Farm:
    return create_farmer_with_farm(db_session, "farmer@example.com", farm_name="Green Acres")


@pytest.fixture
def farmer(db_session: Session, farm: Farm) -> User:
    owner = db_session.get(User, farm.owner_id)
    assert owner is not None
    return owner


@pytest.fixture
def confirmed_offer(db_session: Session, farm: Farm) -> GrowOffer:
    return create_grow_offer(db_session, farm, status=GrowOfferStatus.CONFIRMED)


@pytest.fixture
def customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="customer@example.com")


class TestPostCropUpdate:
    def test_farm_owner_posts_an_update(
        self, client: TestClient, db_session: Session, farmer: User, confirmed_offer: GrowOffer
    ) -> None:
        response = client.post(
            updates_url(confirmed_offer),
            json=update_payload(image_url="https://photos.example.com/okra-seedlings.jpg"),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["grow_offer_id"] == confirmed_offer.id
        assert body["stage"] == "PLANTED"
        assert body["message"] == "Seedlings went into the ground today."
        assert body["image_url"] == "https://photos.example.com/okra-seedlings.jpg"
        assert db_session.get(CropUpdate, body["id"]) is not None

    def test_image_is_optional(
        self, client: TestClient, farmer: User, confirmed_offer: GrowOffer
    ) -> None:
        response = client.post(
            updates_url(confirmed_offer),
            json=update_payload(image_url="   "),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        assert response.json()["image_url"] is None

    def test_offer_in_the_request_body_is_ignored(
        self, client: TestClient, db_session: Session, farmer: User, confirmed_offer: GrowOffer,
        farm: Farm,
    ) -> None:
        other_offer = create_grow_offer(db_session, farm, crop_name="Kale")

        response = client.post(
            updates_url(confirmed_offer),
            json=update_payload(grow_offer_id=other_offer.id),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        assert response.json()["grow_offer_id"] == confirmed_offer.id

    def test_farmer_of_another_farm_cannot_post(
        self, client: TestClient, db_session: Session, confirmed_offer: GrowOffer
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        other_farmer = db_session.get(User, other_farm.owner_id)
        assert other_farmer is not None

        response = client.post(
            updates_url(confirmed_offer), json=update_payload(), headers=auth_headers(other_farmer)
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "You can only manage your own grow offers"}
        assert count_updates(db_session) == 0

    def test_committed_customer_cannot_post(
        self, client: TestClient, db_session: Session, customer: User, confirmed_offer: GrowOffer
    ) -> None:
        create_commitment(db_session, customer, confirmed_offer)

        response = client.post(
            updates_url(confirmed_offer), json=update_payload(), headers=auth_headers(customer)
        )

        assert response.status_code == 403
        assert count_updates(db_session) == 0

    def test_unauthenticated_request_cannot_post(
        self, client: TestClient, db_session: Session, confirmed_offer: GrowOffer
    ) -> None:
        response = client.post(updates_url(confirmed_offer), json=update_payload())

        assert response.status_code == 401
        assert count_updates(db_session) == 0

    def test_update_for_an_unknown_offer_is_not_found(
        self, client: TestClient, farmer: User
    ) -> None:
        response = client.post(
            f"{GROW_OFFERS_URL}/999999/updates", json=update_payload(), headers=auth_headers(farmer)
        )

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "overrides",
        [
            {"message": "   "},
            {"message": "x" * 2001},
            {"stage": "SPROUTING"},
            {"stage": None},
            {"image_url": "http://photos.example.com/okra.jpg"},
            {"image_url": "javascript:alert(1)"},
            {"image_url": "not a link"},
            {"image_url": "https://photos.example.com/" + "a" * 500},
        ],
        ids=[
            "blank message",
            "message too long",
            "unknown stage",
            "missing stage",
            "http image link",
            "script link",
            "malformed link",
            "link too long",
        ],
    )
    def test_invalid_update_is_rejected(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        confirmed_offer: GrowOffer,
        overrides: dict[str, Any],
    ) -> None:
        response = client.post(
            updates_url(confirmed_offer),
            json=update_payload(**overrides),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 422
        assert count_updates(db_session) == 0


class TestStagesAndOfferStatus:
    def test_planned_update_leaves_an_open_offer_open(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        open_offer = create_grow_offer(db_session, farm, status=GrowOfferStatus.OPEN)

        response = client.post(
            updates_url(open_offer), json=update_payload(stage="PLANNED"), headers=auth_headers(farmer)
        )

        assert response.status_code == 201
        db_session.refresh(open_offer)
        assert open_offer.status is GrowOfferStatus.OPEN

    @pytest.mark.parametrize("stage", ["PLANTED", "GROWING", "READY"])
    def test_open_offer_cannot_be_planted_before_it_is_confirmed(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm, stage: str
    ) -> None:
        open_offer = create_grow_offer(db_session, farm, status=GrowOfferStatus.OPEN)

        response = client.post(
            updates_url(open_offer), json=update_payload(stage=stage), headers=auth_headers(farmer)
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "Until the offer is confirmed, only a PLANNED update can be posted"
        }
        assert count_updates(db_session) == 0
        db_session.refresh(open_offer)
        assert open_offer.status is GrowOfferStatus.OPEN

    @pytest.mark.parametrize(
        "stage", ["PLANTED", "GERMINATED", "GROWING", "FLOWERING", "HARVEST_SOON"]
    )
    def test_a_growing_stage_moves_a_confirmed_offer_to_growing(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        confirmed_offer: GrowOffer,
        stage: str,
    ) -> None:
        response = client.post(
            updates_url(confirmed_offer),
            json=update_payload(stage=stage),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        db_session.refresh(confirmed_offer)
        assert confirmed_offer.status is GrowOfferStatus.GROWING

    def test_planned_update_leaves_a_confirmed_offer_confirmed(
        self, client: TestClient, db_session: Session, farmer: User, confirmed_offer: GrowOffer
    ) -> None:
        client.post(
            updates_url(confirmed_offer),
            json=update_payload(stage="PLANNED"),
            headers=auth_headers(farmer),
        )

        db_session.refresh(confirmed_offer)
        assert confirmed_offer.status is GrowOfferStatus.CONFIRMED

    @pytest.mark.parametrize("starting_status", [GrowOfferStatus.CONFIRMED, GrowOfferStatus.GROWING])
    def test_ready_update_makes_the_offer_ready(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        farm: Farm,
        starting_status: GrowOfferStatus,
    ) -> None:
        offer = create_grow_offer(db_session, farm, status=starting_status)

        response = client.post(
            updates_url(offer), json=update_payload(stage="READY"), headers=auth_headers(farmer)
        )

        assert response.status_code == 201
        db_session.refresh(offer)
        assert offer.status is GrowOfferStatus.READY

    def test_the_whole_journey_in_order(
        self, client: TestClient, db_session: Session, farmer: User, confirmed_offer: GrowOffer
    ) -> None:
        statuses = []
        for stage in CropStage:
            response = client.post(
                updates_url(confirmed_offer),
                json=update_payload(stage=stage.value),
                headers=auth_headers(farmer),
            )
            assert response.status_code == 201
            db_session.refresh(confirmed_offer)
            statuses.append(confirmed_offer.status.value)

        assert statuses == [
            "CONFIRMED",
            "GROWING",
            "GROWING",
            "GROWING",
            "GROWING",
            "GROWING",
            "READY",
        ]

    def test_stage_cannot_go_backwards(
        self, client: TestClient, db_session: Session, farmer: User, confirmed_offer: GrowOffer
    ) -> None:
        create_crop_update(db_session, confirmed_offer, stage=CropStage.FLOWERING)

        response = client.post(
            updates_url(confirmed_offer),
            json=update_payload(stage="PLANTED"),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "The crop is already at FLOWERING; updates cannot go back a stage"
        }
        assert count_updates(db_session) == 1

    def test_several_updates_can_share_a_stage(
        self, client: TestClient, db_session: Session, farmer: User, confirmed_offer: GrowOffer
    ) -> None:
        for message in ("First week of growth.", "Second week of growth."):
            response = client.post(
                updates_url(confirmed_offer),
                json=update_payload(stage="GROWING", message=message),
                headers=auth_headers(farmer),
            )
            assert response.status_code == 201

        assert count_updates(db_session) == 2

    @pytest.mark.parametrize("status", [GrowOfferStatus.COMPLETED, GrowOfferStatus.CANCELLED])
    def test_closed_offer_takes_no_more_updates(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        farm: Farm,
        status: GrowOfferStatus,
    ) -> None:
        closed_offer = create_grow_offer(db_session, farm, status=status)

        response = client.post(
            updates_url(closed_offer), json=update_payload(), headers=auth_headers(farmer)
        )

        assert response.status_code == 409
        assert response.json() == {"detail": "This grow offer is closed and takes no more updates"}
        assert count_updates(db_session) == 0


class TestReadCropJourney:
    def test_updates_are_returned_oldest_first(
        self, client: TestClient, db_session: Session, confirmed_offer: GrowOffer
    ) -> None:
        # Inserted latest stage first, so the ids run opposite to the journey.
        growing = create_crop_update(db_session, confirmed_offer, stage=CropStage.GROWING)
        planted = create_crop_update(db_session, confirmed_offer, stage=CropStage.PLANTED)
        planned = create_crop_update(db_session, confirmed_offer, stage=CropStage.PLANNED)
        # Every test runs in one transaction, where now() never advances, so
        # each row is given its own time. The journey must follow the time,
        # not the id.
        for hours_ago, crop_update in ((10, planned), (9, planted), (8, growing)):
            db_session.execute(
                text(
                    "UPDATE crop_updates SET created_at = now() - make_interval(hours => :hours) "
                    "WHERE id = :id"
                ),
                {"hours": hours_ago, "id": crop_update.id},
            )
        db_session.commit()

        response = client.get(updates_url(confirmed_offer))

        assert response.status_code == 200
        assert [crop_update["stage"] for crop_update in response.json()] == [
            "PLANNED",
            "PLANTED",
            "GROWING",
        ]
        timestamps = [crop_update["created_at"] for crop_update in response.json()]
        assert timestamps == sorted(timestamps)

    def test_journey_contains_only_the_offers_own_updates(
        self, client: TestClient, db_session: Session, confirmed_offer: GrowOffer, farm: Farm
    ) -> None:
        other_offer = create_grow_offer(db_session, farm, crop_name="Kale")
        create_crop_update(db_session, confirmed_offer, message="About the okra.")
        create_crop_update(db_session, other_offer, message="About the kale.")

        response = client.get(updates_url(confirmed_offer))

        assert [crop_update["message"] for crop_update in response.json()] == ["About the okra."]

    def test_journey_is_public_and_empty_before_any_update(
        self, client: TestClient, confirmed_offer: GrowOffer
    ) -> None:
        response = client.get(updates_url(confirmed_offer))

        assert response.status_code == 200
        assert response.json() == []

    def test_journey_of_an_unknown_offer_is_not_found(self, client: TestClient) -> None:
        assert client.get(f"{GROW_OFFERS_URL}/999999/updates").status_code == 404


class TestGrowOfferDetail:
    def test_offer_is_returned_with_its_farm_and_progress(
        self,
        client: TestClient,
        db_session: Session,
        confirmed_offer: GrowOffer,
        farm: Farm,
        customer: User,
    ) -> None:
        create_commitment(db_session, customer, confirmed_offer, quantity=8)

        response = client.get(f"{GROW_OFFERS_URL}/{confirmed_offer.id}")

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"offer", "farm"}
        assert body["offer"]["id"] == confirmed_offer.id
        assert body["offer"]["status"] == "CONFIRMED"
        assert body["offer"]["committed_customers"] == 1
        assert body["offer"]["committed_quantity"] == 8
        assert body["farm"] == {
            "id": farm.id,
            "farm_name": "Green Acres",
            "city": "Charlotte",
            "state": "NC",
        }

    def test_unknown_offer_is_not_found(self, client: TestClient) -> None:
        assert client.get(f"{GROW_OFFERS_URL}/999999").status_code == 404


class TestCompleteGrowOffer:
    def test_farmer_completes_an_offer_whose_crop_is_ready(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        ready_offer = create_grow_offer(db_session, farm, status=GrowOfferStatus.READY)

        response = client.post(
            f"{GROW_OFFERS_URL}/{ready_offer.id}/complete", headers=auth_headers(farmer)
        )

        assert response.status_code == 200
        assert response.json()["status"] == "COMPLETED"
        db_session.refresh(ready_offer)
        assert ready_offer.status is GrowOfferStatus.COMPLETED

    @pytest.mark.parametrize(
        "status",
        [
            GrowOfferStatus.OPEN,
            GrowOfferStatus.CONFIRMED,
            GrowOfferStatus.GROWING,
            GrowOfferStatus.COMPLETED,
            GrowOfferStatus.CANCELLED,
        ],
    )
    def test_offer_that_is_not_ready_cannot_be_completed(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        farm: Farm,
        status: GrowOfferStatus,
    ) -> None:
        offer = create_grow_offer(db_session, farm, status=status)

        response = client.post(f"{GROW_OFFERS_URL}/{offer.id}/complete", headers=auth_headers(farmer))

        assert response.status_code == 409
        db_session.refresh(offer)
        assert offer.status is status

    def test_only_the_owner_can_complete_an_offer(
        self, client: TestClient, db_session: Session, farm: Farm, customer: User
    ) -> None:
        ready_offer = create_grow_offer(db_session, farm, status=GrowOfferStatus.READY)
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        other_farmer = db_session.get(User, other_farm.owner_id)
        assert other_farmer is not None
        complete_url = f"{GROW_OFFERS_URL}/{ready_offer.id}/complete"

        assert client.post(complete_url, headers=auth_headers(other_farmer)).status_code == 403
        assert client.post(complete_url, headers=auth_headers(customer)).status_code == 403
        assert client.post(complete_url).status_code == 401
        db_session.refresh(ready_offer)
        assert ready_offer.status is GrowOfferStatus.READY
