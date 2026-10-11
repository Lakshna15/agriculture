from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.product import InventoryHistory, Product
from app.models.reservation import ProductReservation, ReservationStatus
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_farmer_with_farm,
    create_product,
    create_product_reservation,
    create_user,
    days_from_today,
)

RESERVATIONS_URL = "/api/reservations"
MY_RESERVATIONS_URL = "/api/reservations/mine"
FARM_RESERVATIONS_URL = "/api/reservations/farm"


def status_url(reservation_id: int) -> str:
    return f"{RESERVATIONS_URL}/{reservation_id}/status"


def reservation_payload(product: Product, **overrides: Any) -> dict[str, Any]:
    payload = {
        "product_id": product.id,
        "quantity": 3,
        "pickup_date": days_from_today(1).isoformat(),
        "pickup_time": "10:30:00",
    }
    return payload | overrides


def count_reservations(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(ProductReservation)) or 0


def stock_history(db_session: Session, product: Product) -> list[tuple[int, int]]:
    rows = db_session.scalars(
        select(InventoryHistory)
        .where(InventoryHistory.product_id == product.id)
        .order_by(InventoryHistory.id)
    )
    return [(row.previous_quantity, row.new_quantity) for row in rows]


@pytest.fixture
def farm(db_session: Session) -> Farm:
    return create_farmer_with_farm(db_session, "farmer@example.com", farm_name="Green Acres")


@pytest.fixture
def farmer(db_session: Session, farm: Farm) -> User:
    owner = db_session.get(User, farm.owner_id)
    assert owner is not None
    return owner


@pytest.fixture
def product(db_session: Session, farm: Farm) -> Product:
    return create_product(db_session, farm, quantity_available=20)


@pytest.fixture
def customer(db_session: Session) -> User:
    return create_user(
        db_session, role=UserRole.CUSTOMER, email="customer@example.com", name="Ana Grower"
    )


@pytest.fixture
def other_customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="other-customer@example.com")


class TestReserveProduct:
    def test_customer_reserves_a_product(
        self, client: TestClient, db_session: Session, customer: User, product: Product, farm: Farm
    ) -> None:
        response = client.post(
            RESERVATIONS_URL, json=reservation_payload(product), headers=auth_headers(customer)
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "PENDING"
        assert body["quantity"] == 3
        assert body["pickup_date"] == days_from_today(1).isoformat()
        assert body["pickup_time"] == "10:30:00"
        assert body["customer_name"] == "Ana Grower"
        assert body["product"] == {"id": product.id, "name": "Heirloom Tomatoes", "unit": "LB"}
        assert body["farm"]["id"] == farm.id
        assert body["farm"]["farm_name"] == "Green Acres"
        assert body["farm"]["address"] == "100 Orchard Road"

        stored_reservation = db_session.get(ProductReservation, body["id"])
        assert stored_reservation is not None
        assert stored_reservation.customer_id == customer.id

    def test_reserving_deducts_stock_and_records_it_in_the_history(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=3),
            headers=auth_headers(customer),
        )

        db_session.refresh(product)
        assert product.quantity_available == 17
        assert stock_history(db_session, product) == [(20, 17)]

    def test_the_whole_stock_can_be_reserved(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        response = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=20),
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        db_session.refresh(product)
        assert product.quantity_available == 0

    def test_more_than_the_stock_cannot_be_reserved(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        response = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=21),
            headers=auth_headers(customer),
        )

        assert response.status_code == 409
        assert response.json() == {"detail": "Only 20 available"}
        db_session.refresh(product)
        assert product.quantity_available == 20
        assert count_reservations(db_session) == 0
        assert stock_history(db_session, product) == []

    def test_stock_never_goes_negative_across_several_reservations(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        product: Product,
    ) -> None:
        first = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=12),
            headers=auth_headers(customer),
        )
        second = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=12),
            headers=auth_headers(other_customer),
        )
        third = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=8),
            headers=auth_headers(other_customer),
        )

        assert [first.status_code, second.status_code, third.status_code] == [201, 409, 201]
        assert second.json() == {"detail": "Only 8 available"}
        db_session.refresh(product)
        assert product.quantity_available == 0

    @pytest.mark.parametrize("quantity", [0, -2, 1.5, "three", None])
    def test_invalid_quantity_is_rejected(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        product: Product,
        quantity: object,
    ) -> None:
        response = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=quantity),
            headers=auth_headers(customer),
        )

        assert response.status_code == 422
        assert count_reservations(db_session) == 0

    def test_pickup_date_in_the_past_is_rejected(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        response = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, pickup_date=days_from_today(-1).isoformat()),
            headers=auth_headers(customer),
        )

        assert response.status_code == 422
        assert response.json() == {"detail": "Pickup date cannot be in the past"}
        db_session.refresh(product)
        assert product.quantity_available == 20

    def test_pickup_today_is_accepted(
        self, client: TestClient, customer: User, product: Product
    ) -> None:
        response = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, pickup_date=days_from_today(0).isoformat()),
            headers=auth_headers(customer),
        )

        assert response.status_code == 201

    def test_unknown_product_is_not_found(self, client: TestClient, customer: User) -> None:
        response = client.post(
            RESERVATIONS_URL,
            json={
                "product_id": 999999,
                "quantity": 1,
                "pickup_date": days_from_today(1).isoformat(),
                "pickup_time": "10:30:00",
            },
            headers=auth_headers(customer),
        )

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "product_fields",
        [
            {"active": False},
            {"available_from": days_from_today(3)},
            {"available_until": days_from_today(-1)},
        ],
        ids=["deactivated", "not yet in season", "season over"],
    )
    def test_product_that_is_not_on_offer_cannot_be_reserved(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        farm: Farm,
        product_fields: dict[str, Any],
    ) -> None:
        unavailable_product = create_product(db_session, farm, **product_fields)

        response = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(unavailable_product),
            headers=auth_headers(customer),
        )

        assert response.status_code == 409
        assert response.json() == {"detail": "This product is not available to reserve right now"}
        assert count_reservations(db_session) == 0

    def test_farmer_cannot_reserve_a_product(
        self, client: TestClient, db_session: Session, farmer: User, product: Product
    ) -> None:
        response = client.post(
            RESERVATIONS_URL, json=reservation_payload(product), headers=auth_headers(farmer)
        )

        assert response.status_code == 403
        assert count_reservations(db_session) == 0

    def test_unauthenticated_request_cannot_reserve(
        self, client: TestClient, db_session: Session, product: Product
    ) -> None:
        response = client.post(RESERVATIONS_URL, json=reservation_payload(product))

        assert response.status_code == 401
        assert count_reservations(db_session) == 0

    def test_customer_in_the_request_body_is_ignored(
        self, client: TestClient, db_session: Session, customer: User, other_customer: User,
        product: Product,
    ) -> None:
        response = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, customer_id=other_customer.id, status="COMPLETED"),
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        assert response.json()["status"] == "PENDING"
        stored_reservation = db_session.get(ProductReservation, response.json()["id"])
        assert stored_reservation is not None
        assert stored_reservation.customer_id == customer.id

    def test_database_rejects_a_reservation_for_zero_units(
        self, db_session: Session, customer: User, product: Product
    ) -> None:
        with pytest.raises(IntegrityError, match="ck_product_reservations_quantity_positive"):
            create_product_reservation(db_session, customer, product, quantity=0)


class TestListReservations:
    def test_customer_sees_only_their_own_reservations(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        product: Product,
    ) -> None:
        own = create_product_reservation(db_session, customer, product, quantity=2)
        create_product_reservation(db_session, other_customer, product, quantity=5)

        response = client.get(MY_RESERVATIONS_URL, headers=auth_headers(customer))

        assert response.status_code == 200
        assert [reservation["id"] for reservation in response.json()] == [own.id]
        assert response.json()[0]["product"]["name"] == "Heirloom Tomatoes"
        assert response.json()[0]["farm"]["farm_name"] == "Green Acres"

    def test_farmer_sees_reservations_for_their_farm_with_customer_names(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        product: Product,
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        other_product = create_product(db_session, other_farm, name="Neighbor's Corn")
        own = create_product_reservation(db_session, customer, product)
        create_product_reservation(db_session, customer, other_product)

        response = client.get(FARM_RESERVATIONS_URL, headers=auth_headers(farmer))

        assert response.status_code == 200
        assert [reservation["id"] for reservation in response.json()] == [own.id]
        assert response.json()[0]["customer_name"] == "Ana Grower"

    def test_farm_listing_exposes_no_customer_contact_details(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        product: Product,
    ) -> None:
        create_product_reservation(db_session, customer, product)

        response = client.get(FARM_RESERVATIONS_URL, headers=auth_headers(farmer))

        assert customer.email not in response.text
        assert "customer_id" not in response.json()[0]

    def test_farmer_without_a_farm_has_no_reservations(
        self, client: TestClient, db_session: Session
    ) -> None:
        farmer_without_farm = create_user(
            db_session, role=UserRole.FARMER, email="new-farmer@example.com"
        )

        response = client.get(FARM_RESERVATIONS_URL, headers=auth_headers(farmer_without_farm))

        assert response.status_code == 200
        assert response.json() == []

    def test_listings_are_restricted_by_role(
        self, client: TestClient, farmer: User, customer: User
    ) -> None:
        assert client.get(MY_RESERVATIONS_URL, headers=auth_headers(farmer)).status_code == 403
        assert client.get(FARM_RESERVATIONS_URL, headers=auth_headers(customer)).status_code == 403
        assert client.get(MY_RESERVATIONS_URL).status_code == 401
        assert client.get(FARM_RESERVATIONS_URL).status_code == 401


class TestReservationStatus:
    def test_farmer_confirms_then_completes_a_reservation(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        product: Product,
    ) -> None:
        reservation = create_product_reservation(db_session, customer, product)

        confirmed = client.patch(
            status_url(reservation.id), json={"status": "CONFIRMED"}, headers=auth_headers(farmer)
        )
        completed = client.patch(
            status_url(reservation.id), json={"status": "COMPLETED"}, headers=auth_headers(farmer)
        )

        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "CONFIRMED"
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETED"

    def test_completing_a_reservation_leaves_stock_alone(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        product: Product,
    ) -> None:
        created = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=5),
            headers=auth_headers(customer),
        )
        reservation_id = created.json()["id"]

        for new_status in ("CONFIRMED", "COMPLETED"):
            client.patch(
                status_url(reservation_id), json={"status": new_status}, headers=auth_headers(farmer)
            )

        db_session.refresh(product)
        assert product.quantity_available == 15
        assert stock_history(db_session, product) == [(20, 15)]

    @pytest.mark.parametrize("cancelled_by", ["customer", "farmer"])
    @pytest.mark.parametrize("status_when_cancelled", ["PENDING", "CONFIRMED"])
    def test_cancelling_returns_the_reserved_quantity_to_stock(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        product: Product,
        cancelled_by: str,
        status_when_cancelled: str,
    ) -> None:
        created = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=5),
            headers=auth_headers(customer),
        )
        reservation_id = created.json()["id"]
        if status_when_cancelled == "CONFIRMED":
            client.patch(
                status_url(reservation_id), json={"status": "CONFIRMED"}, headers=auth_headers(farmer)
            )
        canceller = customer if cancelled_by == "customer" else farmer

        response = client.patch(
            status_url(reservation_id), json={"status": "CANCELLED"}, headers=auth_headers(canceller)
        )

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"
        db_session.refresh(product)
        assert product.quantity_available == 20
        assert stock_history(db_session, product) == [(20, 15), (15, 20)]

    def test_cancelling_twice_returns_stock_only_once(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        created = client.post(
            RESERVATIONS_URL,
            json=reservation_payload(product, quantity=5),
            headers=auth_headers(customer),
        )
        reservation_id = created.json()["id"]

        first = client.patch(
            status_url(reservation_id), json={"status": "CANCELLED"}, headers=auth_headers(customer)
        )
        second = client.patch(
            status_url(reservation_id), json={"status": "CANCELLED"}, headers=auth_headers(customer)
        )

        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json() == {
            "detail": "A CANCELLED reservation cannot be changed to CANCELLED"
        }
        db_session.refresh(product)
        assert product.quantity_available == 20

    @pytest.mark.parametrize(
        ("current_status", "new_status"),
        [
            (ReservationStatus.PENDING, "COMPLETED"),
            (ReservationStatus.COMPLETED, "CANCELLED"),
            (ReservationStatus.COMPLETED, "CONFIRMED"),
            (ReservationStatus.CANCELLED, "CONFIRMED"),
        ],
    )
    def test_farmer_cannot_make_an_invalid_status_change(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        customer: User,
        product: Product,
        current_status: ReservationStatus,
        new_status: str,
    ) -> None:
        reservation = create_product_reservation(
            db_session, customer, product, status=current_status
        )

        response = client.patch(
            status_url(reservation.id), json={"status": new_status}, headers=auth_headers(farmer)
        )

        assert response.status_code == 409
        db_session.refresh(reservation)
        assert reservation.status is current_status

    @pytest.mark.parametrize("new_status", ["CONFIRMED", "COMPLETED"])
    def test_customer_cannot_confirm_or_complete_their_own_reservation(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        product: Product,
        new_status: str,
    ) -> None:
        reservation = create_product_reservation(db_session, customer, product)

        response = client.patch(
            status_url(reservation.id), json={"status": new_status}, headers=auth_headers(customer)
        )

        assert response.status_code == 403
        db_session.refresh(reservation)
        assert reservation.status is ReservationStatus.PENDING

    def test_another_customer_cannot_cancel_the_reservation(
        self,
        client: TestClient,
        db_session: Session,
        customer: User,
        other_customer: User,
        product: Product,
    ) -> None:
        reservation = create_product_reservation(db_session, customer, product)

        response = client.patch(
            status_url(reservation.id),
            json={"status": "CANCELLED"},
            headers=auth_headers(other_customer),
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "You do not have access to this reservation"}
        db_session.refresh(reservation)
        assert reservation.status is ReservationStatus.PENDING

    def test_farmer_of_another_farm_cannot_change_the_reservation(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
        other_farmer = db_session.get(User, other_farm.owner_id)
        assert other_farmer is not None
        reservation = create_product_reservation(db_session, customer, product)

        response = client.patch(
            status_url(reservation.id),
            json={"status": "CONFIRMED"},
            headers=auth_headers(other_farmer),
        )

        assert response.status_code == 403
        db_session.refresh(reservation)
        assert reservation.status is ReservationStatus.PENDING

    def test_status_change_requires_authentication(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        reservation = create_product_reservation(db_session, customer, product)

        response = client.patch(status_url(reservation.id), json={"status": "CANCELLED"})

        assert response.status_code == 401

    def test_unknown_reservation_is_not_found(self, client: TestClient, farmer: User) -> None:
        response = client.patch(
            status_url(999999), json={"status": "CONFIRMED"}, headers=auth_headers(farmer)
        )

        assert response.status_code == 404

    def test_unknown_status_is_a_validation_error(
        self, client: TestClient, db_session: Session, farmer: User, customer: User, product: Product
    ) -> None:
        reservation = create_product_reservation(db_session, customer, product)

        response = client.patch(
            status_url(reservation.id), json={"status": "SHIPPED"}, headers=auth_headers(farmer)
        )

        assert response.status_code == 422
