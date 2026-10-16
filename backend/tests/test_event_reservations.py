import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.event import EventReservation, FarmEvent
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
)

EVENT_RESERVATIONS_URL = "/api/event-reservations"
MY_EVENT_RESERVATIONS_URL = "/api/event-reservations/mine"
FARM_EVENT_RESERVATIONS_URL = "/api/event-reservations/farm"


def status_url(reservation_id: int) -> str:
    return f"{EVENT_RESERVATIONS_URL}/{reservation_id}/status"


def count_reservations(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(EventReservation)) or 0


def reserved_spots(db_session: Session, event: FarmEvent) -> int:
    """Places taken at an event, counting everything that is not cancelled."""
    return (
        db_session.scalar(
            select(func.coalesce(func.sum(EventReservation.party_size), 0)).where(
                EventReservation.event_id == event.id,
                EventReservation.status != ReservationStatus.CANCELLED,
            )
        )
        or 0
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
def event(db_session: Session, farm: Farm) -> FarmEvent:
    return create_event(db_session, farm, capacity=10)


@pytest.fixture
def customer(db_session: Session) -> User:
    return create_user(
        db_session, role=UserRole.CUSTOMER, email="customer@example.com", name="Ana Grower"
    )


@pytest.fixture
def other_customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="other-customer@example.com")


class TestReserveEvent:
    def test_customer_reserves_places_at_an_event(
        self, client: TestClient, db_session: Session, customer: User, event: FarmEvent, farm: Farm
    ) -> None:
        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 4},
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "PENDING"
        assert body["party_size"] == 4
        assert body["customer_name"] == "Ana Grower"
        assert body["event"]["id"] == event.id
        assert body["event"]["title"] == "Strawberry Picking Morning"
        assert body["event"]["event_date"] == days_from_today(7).isoformat()
        assert body["event"]["price"] == "12.00"
        assert body["farm"]["id"] == farm.id
        assert body["farm"]["farm_name"] == "Green Acres"

        stored_reservation = db_session.get(EventReservation, body["id"])
        assert stored_reservation is not None
        assert stored_reservation.customer_id == customer.id

    def test_event_can_be_filled_exactly_to_capacity(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        event: FarmEvent,
    ) -> None:
        first = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 6},
            headers=auth_headers(customer),
        )
        second = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 4},
            headers=auth_headers(other_customer),
        )

        assert [first.status_code, second.status_code] == [201, 201]
        assert reserved_spots(db_session, event) == 10

    def test_party_larger_than_the_remaining_places_is_refused(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        event: FarmEvent,
    ) -> None:
        create_event_reservation(db_session, customer, event, party_size=7)

        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 4},
            headers=auth_headers(other_customer),
        )

        assert response.status_code == 409
        assert response.json() == {"detail": "Only 3 spots remaining"}
        assert reserved_spots(db_session, event) == 7

    def test_party_larger_than_the_capacity_is_refused(
        self, client: TestClient, db_session: Session, customer: User, event: FarmEvent
    ) -> None:
        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 11},
            headers=auth_headers(customer),
        )

        assert response.status_code == 409
        assert count_reservations(db_session) == 0

    def test_fully_booked_event_refuses_any_further_reservation(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        event: FarmEvent,
    ) -> None:
        create_event_reservation(db_session, customer, event, party_size=10)

        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 1},
            headers=auth_headers(other_customer),
        )

        assert response.status_code == 409
        assert response.json() == {"detail": "This event is fully booked"}
        assert reserved_spots(db_session, event) == 10

    @pytest.mark.parametrize(
        "counted_status",
        [ReservationStatus.PENDING, ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED],
    )
    def test_every_live_reservation_counts_against_capacity(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        event: FarmEvent,
        counted_status: ReservationStatus,
    ) -> None:
        create_event_reservation(db_session, customer, event, party_size=10, status=counted_status)

        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 1},
            headers=auth_headers(other_customer),
        )

        assert response.status_code == 409

    def test_cancelled_reservations_free_their_places(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        event: FarmEvent,
    ) -> None:
        create_event_reservation(
            db_session, customer, event, party_size=10, status=ReservationStatus.CANCELLED
        )

        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 10},
            headers=auth_headers(other_customer),
        )

        assert response.status_code == 201

    def test_cancelling_through_the_api_frees_places_for_someone_else(
        self,
        client: TestClient,
        customer: User,
        other_customer: User,
        event: FarmEvent,
    ) -> None:
        created = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 10},
            headers=auth_headers(customer),
        )
        refused = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 2},
            headers=auth_headers(other_customer),
        )
        client.patch(
            status_url(created.json()["id"]),
            json={"status": "CANCELLED"},
            headers=auth_headers(customer),
        )
        accepted = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 2},
            headers=auth_headers(other_customer),
        )

        assert [refused.status_code, accepted.status_code] == [409, 201]

    @pytest.mark.parametrize("party_size", [0, -1, 2.5, "two", None])
    def test_invalid_party_size_is_rejected(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        event: FarmEvent,
        party_size: object,
    ) -> None:
        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": party_size},
            headers=auth_headers(customer),
        )

        assert response.status_code == 422
        assert count_reservations(db_session) == 0

    def test_event_that_has_already_happened_cannot_be_reserved(
        self, client: TestClient, db_session: Session, customer: User, farm: Farm
    ) -> None:
        past_event = create_event(db_session, farm, event_date=days_from_today(-1))

        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": past_event.id, "party_size": 2},
            headers=auth_headers(customer),
        )

        assert response.status_code == 409
        assert response.json() == {"detail": "This event has already taken place"}
        assert count_reservations(db_session) == 0

    def test_unknown_event_is_not_found(self, client: TestClient, customer: User) -> None:
        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": 999999, "party_size": 2},
            headers=auth_headers(customer),
        )

        assert response.status_code == 404

    def test_farmer_cannot_reserve_an_event(
        self, client: TestClient, db_session: Session, farmer: User, event: FarmEvent
    ) -> None:
        response = client.post(
            EVENT_RESERVATIONS_URL,
            json={"event_id": event.id, "party_size": 2},
            headers=auth_headers(farmer),
        )

        assert response.status_code == 403
        assert count_reservations(db_session) == 0

    def test_unauthenticated_request_cannot_reserve(
        self, client: TestClient, db_session: Session, event: FarmEvent
    ) -> None:
        response = client.post(
            EVENT_RESERVATIONS_URL, json={"event_id": event.id, "party_size": 2}
        )

        assert response.status_code == 401
        assert count_reservations(db_session) == 0

    def test_database_rejects_a_reservation_for_nobody(
        self, db_session: Session, customer: User, event: FarmEvent
    ) -> None:
        with pytest.raises(IntegrityError, match="ck_event_reservations_party_size_positive"):
            create_event_reservation(db_session, customer, event, party_size=0)


class TestListEventReservations:
    def test_customer_sees_only_their_own_event_reservations(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        event: FarmEvent,
    ) -> None:
        own = create_event_reservation(db_session, customer, event, party_size=2)
        create_event_reservation(db_session, other_customer, event, party_size=3)

        response = client.get(MY_EVENT_RESERVATIONS_URL, headers=auth_headers(customer))

        assert response.status_code == 200
        assert [reservation["id"] for reservation in response.json()] == [own.id]
        assert response.json()[0]["event"]["title"] == "Strawberry Picking Morning"

    def test_farmer_sees_reservations_for_their_events_with_customer_names(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        event: FarmEvent,
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        other_event = create_event(db_session, other_farm, title="Neighbor's Tour")
        own = create_event_reservation(db_session, customer, event)
        create_event_reservation(db_session, customer, other_event)

        response = client.get(FARM_EVENT_RESERVATIONS_URL, headers=auth_headers(farmer))

        assert response.status_code == 200
        assert [reservation["id"] for reservation in response.json()] == [own.id]
        assert response.json()[0]["customer_name"] == "Ana Grower"
        assert customer.email not in response.text

    def test_farmer_without_a_farm_has_no_event_reservations(
        self, client: TestClient, db_session: Session
    ) -> None:
        new_farmer = create_user(db_session, role=UserRole.FARMER, email="new-farmer@example.com")

        response = client.get(FARM_EVENT_RESERVATIONS_URL, headers=auth_headers(new_farmer))

        assert response.status_code == 200
        assert response.json() == []

    def test_listings_are_restricted_by_role(
        self, client: TestClient, farmer: User, customer: User
    ) -> None:
        assert client.get(MY_EVENT_RESERVATIONS_URL, headers=auth_headers(farmer)).status_code == 403
        assert (
            client.get(FARM_EVENT_RESERVATIONS_URL, headers=auth_headers(customer)).status_code
            == 403
        )
        assert client.get(MY_EVENT_RESERVATIONS_URL).status_code == 401
        assert client.get(FARM_EVENT_RESERVATIONS_URL).status_code == 401


class TestEventReservationStatus:
    def test_farmer_confirms_then_completes_a_reservation(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        event: FarmEvent,
    ) -> None:
        reservation = create_event_reservation(db_session, customer, event)

        confirmed = client.patch(
            status_url(reservation.id), json={"status": "CONFIRMED"}, headers=auth_headers(farmer)
        )
        completed = client.patch(
            status_url(reservation.id), json={"status": "COMPLETED"}, headers=auth_headers(farmer)
        )

        assert confirmed.json()["status"] == "CONFIRMED"
        assert completed.json()["status"] == "COMPLETED"

    @pytest.mark.parametrize("cancelled_by", ["customer", "farmer"])
    def test_either_side_can_cancel(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        event: FarmEvent,
        cancelled_by: str,
    ) -> None:
        reservation = create_event_reservation(db_session, customer, event, party_size=4)
        canceller = customer if cancelled_by == "customer" else farmer

        response = client.patch(
            status_url(reservation.id),
            json={"status": "CANCELLED"},
            headers=auth_headers(canceller),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"
        assert reserved_spots(db_session, event) == 0

    def test_invalid_status_change_is_a_conflict(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        event: FarmEvent,
    ) -> None:
        reservation = create_event_reservation(
            db_session, customer, event, status=ReservationStatus.COMPLETED
        )

        response = client.patch(
            status_url(reservation.id), json={"status": "CANCELLED"}, headers=auth_headers(farmer)
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "A COMPLETED reservation cannot be changed to CANCELLED"
        }

    def test_customer_cannot_confirm_their_own_reservation(
        self, client: TestClient, db_session: Session, customer: User, event: FarmEvent
    ) -> None:
        reservation = create_event_reservation(db_session, customer, event)

        response = client.patch(
            status_url(reservation.id), json={"status": "CONFIRMED"}, headers=auth_headers(customer)
        )

        assert response.status_code == 403
        db_session.refresh(reservation)
        assert reservation.status is ReservationStatus.PENDING

    def test_people_outside_the_reservation_cannot_change_it(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        event: FarmEvent,
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        other_farmer = db_session.get(User, other_farm.owner_id)
        assert other_farmer is not None
        reservation = create_event_reservation(db_session, customer, event)

        by_other_customer = client.patch(
            status_url(reservation.id),
            json={"status": "CANCELLED"},
            headers=auth_headers(other_customer),
        )
        by_other_farmer = client.patch(
            status_url(reservation.id),
            json={"status": "CONFIRMED"},
            headers=auth_headers(other_farmer),
        )
        anonymous = client.patch(status_url(reservation.id), json={"status": "CANCELLED"})

        assert by_other_customer.status_code == 403
        assert by_other_farmer.status_code == 403
        assert anonymous.status_code == 401
        db_session.refresh(reservation)
        assert reservation.status is ReservationStatus.PENDING

    def test_unknown_reservation_is_not_found(self, client: TestClient, farmer: User) -> None:
        response = client.patch(
            status_url(999999), json={"status": "CONFIRMED"}, headers=auth_headers(farmer)
        )

        assert response.status_code == 404
