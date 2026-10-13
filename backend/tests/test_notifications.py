import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.grow_offer import GrowOffer, GrowOfferStatus
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_commitment,
    create_farmer_with_farm,
    create_grow_offer,
    create_notification,
    create_user,
)

NOTIFICATIONS_URL = "/api/notifications"
UNREAD_COUNT_URL = "/api/notifications/unread-count"
READ_ALL_URL = "/api/notifications/read-all"
COMMITMENTS_URL = "/api/crop-commitments"
GROW_OFFERS_URL = "/api/grow-offers"


def notifications_of(db_session: Session, user: User) -> list[tuple[str, str]]:
    """A user's notifications as (type, message), oldest first."""
    rows = db_session.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.id)
    )
    return [(row.type.value, row.message) for row in rows]


def commit(client: TestClient, customer: User, offer: GrowOffer):
    return client.post(
        COMMITMENTS_URL,
        json={"grow_offer_id": offer.id, "quantity": 5},
        headers=auth_headers(customer),
    )


def post_update(client: TestClient, farmer: User, offer: GrowOffer, stage: str):
    return client.post(
        f"{GROW_OFFERS_URL}/{offer.id}/updates",
        json={"stage": stage, "message": "A note from the field."},
        headers=auth_headers(farmer),
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
def customers(db_session: Session) -> list[User]:
    return [
        create_user(db_session, role=UserRole.CUSTOMER, email=f"customer-{number}@example.com")
        for number in range(1, 5)
    ]


class TestConfirmedNotification:
    def test_every_committed_customer_is_told_when_the_offer_is_confirmed(
        self, client: TestClient, db_session: Session, farm: Farm, customers: list[User]
    ) -> None:
        offer = create_grow_offer(db_session, farm, minimum_customers=3)

        for customer in customers[:3]:
            commit(client, customer, offer)

        expected = [
            (
                "GROW_OFFER_CONFIRMED",
                "Okra at Green Acres is confirmed. "
                "Enough customers committed, so the farm will grow it.",
            )
        ]
        # Including the third customer, whose commitment was the one that confirmed it.
        for customer in customers[:3]:
            assert notifications_of(db_session, customer) == expected

    def test_nobody_is_notified_before_the_threshold_is_reached(
        self, client: TestClient, db_session: Session, farm: Farm, customers: list[User]
    ) -> None:
        offer = create_grow_offer(db_session, farm, minimum_customers=3)

        commit(client, customers[0], offer)
        commit(client, customers[1], offer)

        assert notifications_of(db_session, customers[0]) == []
        assert notifications_of(db_session, customers[1]) == []

    def test_confirmation_is_announced_once_not_on_every_later_commitment(
        self, client: TestClient, db_session: Session, farm: Farm, customers: list[User]
    ) -> None:
        offer = create_grow_offer(db_session, farm, minimum_customers=3)
        for customer in customers[:3]:
            commit(client, customer, offer)

        commit(client, customers[3], offer)

        assert len(notifications_of(db_session, customers[0])) == 1
        # Someone who joins an offer that is already confirmed has nothing to be told.
        assert notifications_of(db_session, customers[3]) == []

    def test_customers_who_did_not_commit_and_the_farmer_are_not_notified(
        self,
        client: TestClient,
        db_session: Session,
        farm: Farm,
        farmer: User,
        customers: list[User],
    ) -> None:
        offer = create_grow_offer(db_session, farm, minimum_customers=1)

        commit(client, customers[0], offer)

        assert len(notifications_of(db_session, customers[0])) == 1
        assert notifications_of(db_session, customers[1]) == []
        assert notifications_of(db_session, farmer) == []


class TestCropUpdateNotifications:
    def test_committed_customers_are_told_about_a_crop_update(
        self,
        client: TestClient,
        db_session: Session,
        farm: Farm,
        farmer: User,
        customers: list[User],
    ) -> None:
        offer = create_grow_offer(db_session, farm, status=GrowOfferStatus.CONFIRMED)
        create_commitment(db_session, customers[0], offer)
        create_commitment(db_session, customers[1], offer)

        post_update(client, farmer, offer, "PLANTED")

        expected = [
            ("CROP_UPDATE_POSTED", "Green Acres posted an update: your Okra has been planted.")
        ]
        assert notifications_of(db_session, customers[0]) == expected
        assert notifications_of(db_session, customers[1]) == expected
        assert notifications_of(db_session, customers[2]) == []

    def test_customers_are_told_once_when_the_crop_becomes_ready(
        self,
        client: TestClient,
        db_session: Session,
        farm: Farm,
        farmer: User,
        customers: list[User],
    ) -> None:
        offer = create_grow_offer(db_session, farm, status=GrowOfferStatus.GROWING)
        create_commitment(db_session, customers[0], offer)

        post_update(client, farmer, offer, "READY")

        # One message announcing readiness, not a second generic update notice as well.
        assert notifications_of(db_session, customers[0]) == [
            ("CROP_READY", "Your Okra from Green Acres is ready.")
        ]

    def test_a_further_update_after_ready_is_an_ordinary_update(
        self,
        client: TestClient,
        db_session: Session,
        farm: Farm,
        farmer: User,
        customers: list[User],
    ) -> None:
        offer = create_grow_offer(db_session, farm, status=GrowOfferStatus.GROWING)
        create_commitment(db_session, customers[0], offer)
        post_update(client, farmer, offer, "READY")

        post_update(client, farmer, offer, "READY")

        assert [kind for kind, _message in notifications_of(db_session, customers[0])] == [
            "CROP_READY",
            "CROP_UPDATE_POSTED",
        ]

    def test_a_rejected_update_notifies_nobody(
        self,
        client: TestClient,
        db_session: Session,
        farm: Farm,
        farmer: User,
        customers: list[User],
    ) -> None:
        open_offer = create_grow_offer(db_session, farm, status=GrowOfferStatus.OPEN)
        create_commitment(db_session, customers[0], open_offer)

        response = post_update(client, farmer, open_offer, "PLANTED")

        assert response.status_code == 409
        assert notifications_of(db_session, customers[0]) == []


def test_committed_customers_are_told_when_the_offer_is_cancelled(
    client: TestClient, db_session: Session, farm: Farm, farmer: User, customers: list[User]
) -> None:
    offer = create_grow_offer(db_session, farm)
    create_commitment(db_session, customers[0], offer)

    client.post(f"{GROW_OFFERS_URL}/{offer.id}/cancel", headers=auth_headers(farmer))

    assert notifications_of(db_session, customers[0]) == [
        ("GROW_OFFER_CANCELLED", "Green Acres cancelled the grow offer for Okra.")
    ]
    assert notifications_of(db_session, customers[1]) == []


class TestReadNotifications:
    def test_user_sees_their_own_notifications_newest_first(
        self, client: TestClient, db_session: Session, customers: list[User]
    ) -> None:
        older = create_notification(db_session, customers[0], message="Older message.")
        newer = create_notification(
            db_session,
            customers[0],
            message="Newer message.",
            notification_type=NotificationType.CROP_READY,
        )
        create_notification(db_session, customers[1], message="For someone else.")
        # now() is fixed inside a test's transaction, so the older row is aged explicitly.
        db_session.execute(
            text("UPDATE notifications SET created_at = created_at - interval '1 hour' WHERE id = :id"),
            {"id": older.id},
        )
        db_session.commit()

        response = client.get(NOTIFICATIONS_URL, headers=auth_headers(customers[0]))

        assert response.status_code == 200
        body = response.json()
        assert [notification["id"] for notification in body] == [newer.id, older.id]
        assert set(body[0]) == {"id", "type", "message", "read", "created_at"}
        assert body[0]["type"] == "CROP_READY"
        assert body[0]["message"] == "Newer message."
        assert body[0]["read"] is False

    def test_notifications_work_for_any_role_and_start_empty(
        self, client: TestClient, farmer: User
    ) -> None:
        response = client.get(NOTIFICATIONS_URL, headers=auth_headers(farmer))

        assert response.status_code == 200
        assert response.json() == []

    def test_unread_count_counts_only_the_users_unread_notifications(
        self, client: TestClient, db_session: Session, customers: list[User]
    ) -> None:
        create_notification(db_session, customers[0])
        create_notification(db_session, customers[0])
        create_notification(db_session, customers[0], read=True)
        create_notification(db_session, customers[1])

        response = client.get(UNREAD_COUNT_URL, headers=auth_headers(customers[0]))

        assert response.status_code == 200
        assert response.json() == {"unread": 2}

    def test_user_marks_one_notification_as_read(
        self, client: TestClient, db_session: Session, customers: list[User]
    ) -> None:
        first = create_notification(db_session, customers[0])
        second = create_notification(db_session, customers[0])

        response = client.post(
            f"{NOTIFICATIONS_URL}/{first.id}/read", headers=auth_headers(customers[0])
        )

        assert response.status_code == 200
        assert response.json()["read"] is True
        db_session.refresh(first)
        db_session.refresh(second)
        assert first.read is True
        assert second.read is False
        assert client.get(UNREAD_COUNT_URL, headers=auth_headers(customers[0])).json() == {
            "unread": 1
        }

    def test_another_users_notification_is_reported_as_not_found_and_left_unread(
        self, client: TestClient, db_session: Session, customers: list[User]
    ) -> None:
        notification = create_notification(db_session, customers[0])

        response = client.post(
            f"{NOTIFICATIONS_URL}/{notification.id}/read", headers=auth_headers(customers[1])
        )

        assert response.status_code == 404
        db_session.refresh(notification)
        assert notification.read is False

    def test_unknown_notification_is_not_found(
        self, client: TestClient, customers: list[User]
    ) -> None:
        response = client.post(
            f"{NOTIFICATIONS_URL}/999999/read", headers=auth_headers(customers[0])
        )

        assert response.status_code == 404

    def test_marking_all_as_read_touches_only_the_users_own_notifications(
        self, client: TestClient, db_session: Session, customers: list[User]
    ) -> None:
        own = [create_notification(db_session, customers[0]) for _ in range(3)]
        someone_elses = create_notification(db_session, customers[1])

        response = client.post(READ_ALL_URL, headers=auth_headers(customers[0]))

        assert response.status_code == 204
        for notification in own:
            db_session.refresh(notification)
            assert notification.read is True
        db_session.refresh(someone_elses)
        assert someone_elses.read is False

    def test_every_notification_endpoint_requires_authentication(
        self, client: TestClient, db_session: Session, customers: list[User]
    ) -> None:
        notification = create_notification(db_session, customers[0])

        assert client.get(NOTIFICATIONS_URL).status_code == 401
        assert client.get(UNREAD_COUNT_URL).status_code == 401
        assert client.post(READ_ALL_URL).status_code == 401
        assert client.post(f"{NOTIFICATIONS_URL}/{notification.id}/read").status_code == 401
        db_session.refresh(notification)
        assert notification.read is False


def test_notifications_from_the_whole_grow_on_demand_flow(
    client: TestClient, db_session: Session, farm: Farm, farmer: User, customers: list[User]
) -> None:
    """A customer follows one crop from commitment to harvest through the API."""
    offer = create_grow_offer(db_session, farm, minimum_customers=2)
    commit(client, customers[0], offer)
    commit(client, customers[1], offer)
    post_update(client, farmer, offer, "PLANTED")
    post_update(client, farmer, offer, "FLOWERING")
    post_update(client, farmer, offer, "READY")

    response = client.get(NOTIFICATIONS_URL, headers=auth_headers(customers[0]))

    assert sorted(notification["type"] for notification in response.json()) == [
        "CROP_READY",
        "CROP_UPDATE_POSTED",
        "CROP_UPDATE_POSTED",
        "GROW_OFFER_CONFIRMED",
    ]
    assert client.get(UNREAD_COUNT_URL, headers=auth_headers(customers[0])).json() == {"unread": 4}
