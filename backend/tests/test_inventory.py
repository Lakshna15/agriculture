import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
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


def inventory_url(product: Product) -> str:
    return f"{PRODUCTS_URL}/{product.id}/inventory"


def history_of(db_session: Session, product_id: int) -> list[tuple[int, int]]:
    """A product's stock changes, oldest first, as (previous, new) pairs."""
    rows = db_session.scalars(
        select(InventoryHistory)
        .where(InventoryHistory.product_id == product_id)
        .order_by(InventoryHistory.id)
    )
    return [(row.previous_quantity, row.new_quantity) for row in rows]


@pytest.fixture
def farmer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.FARMER, email="farmer@example.com")


@pytest.fixture
def farm(db_session: Session, farmer: User) -> Farm:
    return create_farm(db_session, farmer)


@pytest.fixture
def product(db_session: Session, farm: Farm) -> Product:
    return create_product(db_session, farm, quantity_available=20)


def test_creating_a_product_records_its_opening_stock(
    client: TestClient, db_session: Session, farmer: User, farm: Farm
) -> None:
    response = client.post(
        PRODUCTS_URL, json=product_payload(quantity_available=40), headers=auth_headers(farmer)
    )

    assert response.status_code == 201
    assert response.json()["quantity_available"] == 40
    assert history_of(db_session, response.json()["id"]) == [(0, 40)]


def test_creating_a_product_with_no_stock_records_nothing(
    client: TestClient, db_session: Session, farmer: User, farm: Farm
) -> None:
    response = client.post(
        PRODUCTS_URL, json=product_payload(quantity_available=0), headers=auth_headers(farmer)
    )

    assert response.status_code == 201
    assert history_of(db_session, response.json()["id"]) == []


def test_inventory_update_changes_the_stock_and_records_history(
    client: TestClient, db_session: Session, farmer: User, product: Product
) -> None:
    response = client.patch(
        inventory_url(product), json={"quantity_available": 35}, headers=auth_headers(farmer)
    )

    assert response.status_code == 200
    assert response.json()["quantity_available"] == 35
    db_session.refresh(product)
    assert product.quantity_available == 35
    assert history_of(db_session, product.id) == [(20, 35)]


def test_every_inventory_update_adds_one_history_row_in_order(
    client: TestClient, db_session: Session, farmer: User, product: Product
) -> None:
    for quantity in (35, 12, 0, 50):
        response = client.patch(
            inventory_url(product),
            json={"quantity_available": quantity},
            headers=auth_headers(farmer),
        )
        assert response.status_code == 200

    assert history_of(db_session, product.id) == [(20, 35), (35, 12), (12, 0), (0, 50)]


def test_history_rows_carry_a_timestamp(
    client: TestClient, db_session: Session, farmer: User, product: Product
) -> None:
    client.patch(
        inventory_url(product), json={"quantity_available": 5}, headers=auth_headers(farmer)
    )

    history_row = db_session.scalar(
        select(InventoryHistory).where(InventoryHistory.product_id == product.id)
    )
    assert history_row is not None
    assert history_row.changed_at is not None
    assert history_row.changed_at.tzinfo is not None


def test_setting_the_same_quantity_records_nothing(
    client: TestClient, db_session: Session, farmer: User, product: Product
) -> None:
    response = client.patch(
        inventory_url(product), json={"quantity_available": 20}, headers=auth_headers(farmer)
    )

    assert response.status_code == 200
    assert response.json()["quantity_available"] == 20
    assert history_of(db_session, product.id) == []


@pytest.mark.parametrize("quantity", [-1, 2.5, "many", None, 1_000_001])
def test_invalid_quantity_is_rejected_and_nothing_changes(
    client: TestClient, db_session: Session, farmer: User, product: Product, quantity: object
) -> None:
    response = client.patch(
        inventory_url(product), json={"quantity_available": quantity}, headers=auth_headers(farmer)
    )

    assert response.status_code == 422
    db_session.refresh(product)
    assert product.quantity_available == 20
    assert history_of(db_session, product.id) == []


def test_farmer_cannot_change_the_inventory_of_another_farm(
    client: TestClient, db_session: Session, farmer: User, farm: Farm
) -> None:
    other_farm = create_farmer_with_farm(db_session, "other-farmer@example.com")
    other_product = create_product(db_session, other_farm, quantity_available=8)

    response = client.patch(
        inventory_url(other_product), json={"quantity_available": 0}, headers=auth_headers(farmer)
    )

    assert response.status_code == 403
    db_session.refresh(other_product)
    assert other_product.quantity_available == 8
    assert history_of(db_session, other_product.id) == []


def test_customer_cannot_change_inventory(
    client: TestClient, db_session: Session, product: Product
) -> None:
    customer = create_user(db_session, role=UserRole.CUSTOMER, email="customer@example.com")

    response = client.patch(
        inventory_url(product), json={"quantity_available": 0}, headers=auth_headers(customer)
    )

    assert response.status_code == 403
    assert history_of(db_session, product.id) == []


def test_unauthenticated_request_cannot_change_inventory(
    client: TestClient, db_session: Session, product: Product
) -> None:
    response = client.patch(inventory_url(product), json={"quantity_available": 0})

    assert response.status_code == 401
    assert history_of(db_session, product.id) == []


def test_inventory_update_for_an_unknown_product_is_not_found(
    client: TestClient, farmer: User, farm: Farm
) -> None:
    response = client.patch(
        f"{PRODUCTS_URL}/999999/inventory",
        json={"quantity_available": 5},
        headers=auth_headers(farmer),
    )

    assert response.status_code == 404


def test_database_rejects_a_history_row_that_records_no_change(
    db_session: Session, product: Product
) -> None:
    db_session.add(InventoryHistory(product_id=product.id, previous_quantity=7, new_quantity=7))

    with pytest.raises(IntegrityError, match="ck_inventory_history_quantity_changed"):
        db_session.commit()
