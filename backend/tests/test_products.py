from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.product import InventoryHistory, Product
from app.models.user import User, UserRole
from tests.helpers import (
    auth_headers,
    create_farm,
    create_farmer_with_farm,
    create_product,
    create_user,
    product_payload,
)

PRODUCTS_URL = "/api/products"
MY_PRODUCTS_URL = "/api/products/mine"


def count_products(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(Product)) or 0


def count_history_rows(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(InventoryHistory)) or 0


@pytest.fixture
def farmer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.FARMER, email="farmer@example.com")


@pytest.fixture
def farm(db_session: Session, farmer: User) -> Farm:
    return create_farm(db_session, farmer)


@pytest.fixture
def other_farm(db_session: Session) -> Farm:
    return create_farmer_with_farm(
        db_session, "other-farmer@example.com", farm_name="Neighbor Farm"
    )


@pytest.fixture
def customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="customer@example.com")


class TestCreateProduct:
    def test_farmer_creates_a_product_on_their_farm(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        response = client.post(
            PRODUCTS_URL,
            json=product_payload(harvest_date="2026-06-01", available_until="2026-06-30"),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["farm_id"] == farm.id
        assert body["name"] == "Heirloom Tomatoes"
        assert body["category"] == "VEGETABLES"
        assert body["unit"] == "LB"
        assert body["quantity_available"] == 20
        assert body["harvest_date"] == "2026-06-01"
        assert body["available_from"] is None
        assert body["available_until"] == "2026-06-30"
        assert body["organic"] is True
        assert body["active"] is True

        stored_product = db_session.get(Product, body["id"])
        assert stored_product is not None
        assert stored_product.farm_id == farm.id

    def test_price_is_stored_and_returned_as_an_exact_decimal(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        response = client.post(
            PRODUCTS_URL, json=product_payload(price="0.10"), headers=auth_headers(farmer)
        )

        # A binary float cannot hold 0.10 exactly; the API keeps it as text.
        assert response.json()["price"] == "0.10"
        stored_product = db_session.get(Product, response.json()["id"])
        assert stored_product is not None
        assert stored_product.price == Decimal("0.10")

    @pytest.mark.parametrize(("sent", "returned"), [("4.5", "4.50"), ("7", "7.00"), (3, "3.00")])
    def test_price_is_always_returned_with_two_decimal_places(
        self, client: TestClient, farmer: User, farm: Farm, sent: object, returned: str
    ) -> None:
        response = client.post(
            PRODUCTS_URL, json=product_payload(price=sent), headers=auth_headers(farmer)
        )

        assert response.status_code == 201
        assert response.json()["price"] == returned

    def test_farmer_without_a_farm_cannot_create_a_product(
        self, client: TestClient, db_session: Session, farmer: User
    ) -> None:
        response = client.post(PRODUCTS_URL, json=product_payload(), headers=auth_headers(farmer))

        assert response.status_code == 409
        assert response.json() == {"detail": "Create your farm first"}
        assert count_products(db_session) == 0

    def test_customer_cannot_create_a_product(
        self, client: TestClient, db_session: Session, farm: Farm, customer: User
    ) -> None:
        response = client.post(PRODUCTS_URL, json=product_payload(), headers=auth_headers(customer))

        assert response.status_code == 403
        assert count_products(db_session) == 0

    def test_unauthenticated_request_cannot_create_a_product(
        self, client: TestClient, db_session: Session, farm: Farm
    ) -> None:
        response = client.post(PRODUCTS_URL, json=product_payload())

        assert response.status_code == 401
        assert count_products(db_session) == 0

    def test_farm_in_the_request_body_is_ignored(
        self, client: TestClient, farmer: User, farm: Farm, other_farm: Farm
    ) -> None:
        response = client.post(
            PRODUCTS_URL,
            json=product_payload(farm_id=other_farm.id),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 201
        assert response.json()["farm_id"] == farm.id

    @pytest.mark.parametrize(
        "overrides",
        [
            {"name": "  "},
            {"price": "0"},
            {"price": "-1.00"},
            {"price": "4.999"},
            {"price": "free"},
            {"quantity_available": -1},
            {"quantity_available": 1.5},
            {"category": "FURNITURE"},
            {"unit": "BARREL"},
            {"harvest_date": "yesterday"},
            {"available_from": "2026-07-10", "available_until": "2026-07-01"},
        ],
        ids=[
            "blank name",
            "zero price",
            "negative price",
            "fractional cents",
            "price not a number",
            "negative quantity",
            "fractional quantity",
            "unknown category",
            "unknown unit",
            "malformed date",
            "window ends before it starts",
        ],
    )
    def test_invalid_product_is_rejected(
        self,
        client: TestClient,
        db_session: Session,
        farmer: User,
        farm: Farm,
        overrides: dict[str, Any],
    ) -> None:
        response = client.post(
            PRODUCTS_URL, json=product_payload(**overrides), headers=auth_headers(farmer)
        )

        assert response.status_code == 422
        assert count_products(db_session) == 0

    def test_database_rejects_a_non_positive_price(self, db_session: Session, farm: Farm) -> None:
        with pytest.raises(IntegrityError, match="ck_products_price_positive"):
            create_product(db_session, farm, price="0")

    def test_database_rejects_a_negative_quantity(self, db_session: Session, farm: Farm) -> None:
        with pytest.raises(IntegrityError, match="ck_products_quantity_not_negative"):
            create_product(db_session, farm, quantity_available=-5)


class TestUpdateProduct:
    def test_farmer_updates_their_own_product(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        product = create_product(db_session, farm)

        response = client.put(
            f"{PRODUCTS_URL}/{product.id}",
            json=product_payload(name="Cherry Tomatoes", price="6.25", unit="PINT", organic=False),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Cherry Tomatoes"
        assert body["price"] == "6.25"
        assert body["unit"] == "PINT"
        assert body["organic"] is False
        db_session.refresh(product)
        assert product.name == "Cherry Tomatoes"

    def test_farmer_cannot_update_a_product_of_another_farm(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm, other_farm: Farm
    ) -> None:
        other_product = create_product(db_session, other_farm, name="Neighbor's Corn")

        response = client.put(
            f"{PRODUCTS_URL}/{other_product.id}",
            json=product_payload(name="Hijacked"),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "You can only manage your own products"}
        db_session.refresh(other_product)
        assert other_product.name == "Neighbor's Corn"

    def test_farmer_without_a_farm_cannot_update_any_product(
        self, client: TestClient, db_session: Session, farmer: User, other_farm: Farm
    ) -> None:
        other_product = create_product(db_session, other_farm)

        response = client.put(
            f"{PRODUCTS_URL}/{other_product.id}",
            json=product_payload(name="Hijacked"),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 403

    def test_customer_cannot_update_a_product(
        self, client: TestClient, db_session: Session, farm: Farm, customer: User
    ) -> None:
        product = create_product(db_session, farm)

        response = client.put(
            f"{PRODUCTS_URL}/{product.id}",
            json=product_payload(name="Hijacked"),
            headers=auth_headers(customer),
        )

        assert response.status_code == 403

    def test_updating_an_unknown_product_is_not_found(
        self, client: TestClient, farmer: User, farm: Farm
    ) -> None:
        response = client.put(
            f"{PRODUCTS_URL}/999999", json=product_payload(), headers=auth_headers(farmer)
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Product not found"}

    def test_product_can_be_deactivated_and_reactivated(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        product = create_product(db_session, farm)

        deactivate_response = client.put(
            f"{PRODUCTS_URL}/{product.id}",
            json=product_payload(active=False),
            headers=auth_headers(farmer),
        )
        assert deactivate_response.status_code == 200
        assert deactivate_response.json()["active"] is False

        reactivate_response = client.put(
            f"{PRODUCTS_URL}/{product.id}",
            json=product_payload(active=True),
            headers=auth_headers(farmer),
        )
        assert reactivate_response.json()["active"] is True

    def test_update_cannot_change_stock_or_move_the_product_to_another_farm(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm, other_farm: Farm
    ) -> None:
        product = create_product(db_session, farm, quantity_available=20)

        response = client.put(
            f"{PRODUCTS_URL}/{product.id}",
            json=product_payload(quantity_available=500, farm_id=other_farm.id),
            headers=auth_headers(farmer),
        )

        assert response.status_code == 200
        assert response.json()["quantity_available"] == 20
        assert response.json()["farm_id"] == farm.id
        assert count_history_rows(db_session) == 0


class TestListMyProducts:
    def test_farmer_sees_only_their_own_products_including_inactive_ones(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm, other_farm: Farm
    ) -> None:
        create_product(db_session, farm, name="Tomatoes")
        create_product(db_session, farm, name="Retired Squash", active=False)
        create_product(db_session, other_farm, name="Neighbor's Corn")

        response = client.get(MY_PRODUCTS_URL, headers=auth_headers(farmer))

        assert response.status_code == 200
        assert [product["name"] for product in response.json()] == ["Retired Squash", "Tomatoes"]

    def test_farmer_without_a_farm_has_no_products(self, client: TestClient, farmer: User) -> None:
        response = client.get(MY_PRODUCTS_URL, headers=auth_headers(farmer))

        assert response.status_code == 200
        assert response.json() == []

    def test_customer_cannot_list_farmer_products(
        self, client: TestClient, customer: User
    ) -> None:
        response = client.get(MY_PRODUCTS_URL, headers=auth_headers(customer))

        assert response.status_code == 403
