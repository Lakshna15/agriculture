"""What the marketplace records for the analytics pipeline, and what it leaves out."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.application_event import ApplicationEvent, ApplicationEventType
from app.models.farm import Farm
from app.models.product import Product
from app.models.user import User, UserRole
from app.services.application_events import record_event, region_coordinate
from tests.helpers import (
    auth_headers,
    create_event,
    create_farmer_with_farm,
    create_grow_offer,
    create_product,
    create_user,
    crop_request_payload,
    days_from_today,
    grow_offer_payload,
)

SEARCH_URL = "/api/products/search"
# Uptown Charlotte, where the helpers put farms, given with more precision
# than a region keeps.
SEARCH_POINT = {"latitude": 35.22719, "longitude": -80.84311}


def events_of(db_session: Session, event_type: ApplicationEventType) -> list[ApplicationEvent]:
    statement = (
        select(ApplicationEvent)
        .where(ApplicationEvent.event_type == event_type)
        .order_by(ApplicationEvent.id)
    )
    return list(db_session.scalars(statement))


def all_events(db_session: Session) -> list[ApplicationEvent]:
    return list(db_session.scalars(select(ApplicationEvent).order_by(ApplicationEvent.id)))


@pytest.fixture
def farm(db_session: Session) -> Farm:
    return create_farmer_with_farm(db_session, "farmer@example.com")


@pytest.fixture
def farmer(db_session: Session, farm: Farm) -> User:
    return db_session.get(User, farm.owner_id)


@pytest.fixture
def customer(db_session: Session) -> User:
    return create_user(db_session, role=UserRole.CUSTOMER, email="customer@example.com")


@pytest.fixture
def product(db_session: Session, farm: Farm) -> Product:
    return create_product(db_session, farm, name="Heirloom Tomatoes", quantity_available=20)


class TestProductSearch:
    def test_a_search_records_the_search_and_every_listing_it_showed(
        self, client: TestClient, db_session: Session, farm: Farm, product: Product
    ) -> None:
        cherry = create_product(db_session, farm, name="Cherry Tomatoes")

        response = client.get(SEARCH_URL, params=SEARCH_POINT | {"query": "  tomatoes "})

        assert response.status_code == 200
        [search] = events_of(db_session, ApplicationEventType.SEARCH_PERFORMED)
        assert search.user_id is None
        assert search.event_metadata == {
            "search_id": search.event_metadata["search_id"],
            "search_term": "Tomatoes",
            "category": None,
            "radius_miles": 25.0,
            "available_only": True,
            "sort": "distance",
            "result_count": 2,
            "region_latitude": 35.2,
            "region_longitude": -80.8,
        }
        assert events_of(db_session, ApplicationEventType.NO_SEARCH_RESULT) == []

        search_id = search.event_metadata["search_id"]
        views = events_of(db_session, ApplicationEventType.PRODUCT_VIEWED)
        assert [(view.product_id, view.farm_id) for view in views] == [
            (result["product"]["id"], farm.id) for result in response.json()
        ]
        assert {view.product_id for view in views} == {product.id, cherry.id}
        assert [view.event_metadata for view in views] == [
            {"search_id": search_id, "position": 1},
            {"search_id": search_id, "position": 2},
        ]

        # One farm view per farm shown, however many of its products appeared.
        [farm_view] = events_of(db_session, ApplicationEventType.FARM_VIEWED)
        assert farm_view.farm_id == farm.id
        assert farm_view.event_metadata == {"search_id": search_id, "source": "product_search"}

    def test_a_search_that_finds_nothing_is_also_recorded_as_no_search_result(
        self, client: TestClient, db_session: Session, product: Product
    ) -> None:
        response = client.get(
            SEARCH_URL, params=SEARCH_POINT | {"query": "okra", "category": "VEGETABLES"}
        )

        assert response.json() == []
        [search] = events_of(db_session, ApplicationEventType.SEARCH_PERFORMED)
        [no_result] = events_of(db_session, ApplicationEventType.NO_SEARCH_RESULT)
        assert no_result.event_metadata == search.event_metadata
        assert no_result.event_metadata["search_term"] == "Okra"
        assert no_result.event_metadata["category"] == "VEGETABLES"
        assert no_result.event_metadata["result_count"] == 0
        assert events_of(db_session, ApplicationEventType.PRODUCT_VIEWED) == []
        assert events_of(db_session, ApplicationEventType.FARM_VIEWED) == []

    def test_browsing_without_a_search_term_records_no_term(
        self, client: TestClient, db_session: Session, product: Product
    ) -> None:
        client.get(SEARCH_URL, params=SEARCH_POINT)

        [search] = events_of(db_session, ApplicationEventType.SEARCH_PERFORMED)
        assert search.event_metadata["search_term"] is None

    def test_search_events_keep_the_region_but_never_the_point_searched_from(
        self, client: TestClient, db_session: Session, product: Product
    ) -> None:
        client.get(SEARCH_URL, params=SEARCH_POINT | {"query": "tomatoes"})
        client.get(SEARCH_URL, params=SEARCH_POINT | {"query": "okra"})

        events = all_events(db_session)
        recorded = json.dumps([event.event_metadata for event in events])
        assert "35.22719" not in recorded
        assert "80.84311" not in recorded
        for event in events:
            assert not {"latitude", "longitude"} & set(event.event_metadata)

    def test_search_events_carry_no_user_even_when_a_customer_is_signed_in(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        client.get(SEARCH_URL, params=SEARCH_POINT, headers=auth_headers(customer))

        assert {event.user_id for event in all_events(db_session)} == {None}

    def test_a_failure_to_record_does_not_break_the_search(
        self,
        client: TestClient,
        db_session: Session,
        product: Product,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        def unavailable_database() -> None:
            raise OperationalError("COMMIT", {}, Exception("the database went away"))

        monkeypatch.setattr(db_session, "commit", unavailable_database)

        with caplog.at_level(logging.ERROR, logger="app.services.application_events"):
            response = client.get(SEARCH_URL, params=SEARCH_POINT | {"query": "tomatoes"})

        assert response.status_code == 200
        assert [result["product"]["name"] for result in response.json()] == ["Heirloom Tomatoes"]
        assert all_events(db_session) == []
        assert "Could not record a product search" in caplog.text


@pytest.mark.parametrize(
    ("degrees", "region"),
    [(35.2271, 35.2), (35.25, 35.3), (35.24999, 35.2), (-80.85, -80.9), (-80.8431, -80.8), (0.04, 0.0)],
)
def test_regions_round_half_away_from_zero_like_postgresql(degrees: float, region: float) -> None:
    assert region_coordinate(degrees) == region


class TestFarmProfile:
    def test_reading_a_farm_profile_records_an_anonymous_farm_view(
        self, client: TestClient, db_session: Session, farm: Farm
    ) -> None:
        response = client.get(f"/api/farms/{farm.id}")

        assert response.status_code == 200
        [view] = events_of(db_session, ApplicationEventType.FARM_VIEWED)
        assert (view.farm_id, view.user_id) == (farm.id, None)
        assert view.event_metadata == {"source": "farm_profile"}

    def test_a_missing_farm_records_nothing(self, client: TestClient, db_session: Session) -> None:
        assert client.get("/api/farms/999999").status_code == 404
        assert all_events(db_session) == []


class TestReservations:
    def test_reserving_a_product_records_who_reserved_what_from_which_farm(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        pickup_date = days_from_today(2).isoformat()

        response = client.post(
            "/api/reservations",
            json={"product_id": product.id, "quantity": 3, "pickup_date": pickup_date, "pickup_time": "10:30:00"},
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        [event] = events_of(db_session, ApplicationEventType.RESERVATION_CREATED)
        assert (event.user_id, event.farm_id, event.product_id) == (customer.id, product.farm_id, product.id)
        assert event.event_metadata == {
            "reservation_id": response.json()["id"],
            "quantity": 3,
            "pickup_date": pickup_date,
        }

    def test_a_refused_reservation_records_nothing(
        self, client: TestClient, db_session: Session, customer: User, product: Product
    ) -> None:
        response = client.post(
            "/api/reservations",
            json={
                "product_id": product.id,
                "quantity": 21,
                "pickup_date": days_from_today(2).isoformat(),
                "pickup_time": "10:30:00",
            },
            headers=auth_headers(customer),
        )

        assert response.status_code == 409
        assert events_of(db_session, ApplicationEventType.RESERVATION_CREATED) == []

    def test_booking_a_farm_event_records_the_booking(
        self, client: TestClient, db_session: Session, customer: User, farm: Farm
    ) -> None:
        event = create_event(db_session, farm, capacity=10)

        response = client.post(
            "/api/event-reservations",
            json={"event_id": event.id, "party_size": 4},
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        [booking] = events_of(db_session, ApplicationEventType.FARM_EVENT_BOOKED)
        assert (booking.user_id, booking.farm_id, booking.product_id) == (customer.id, farm.id, None)
        assert booking.event_metadata == {
            "event_reservation_id": response.json()["id"],
            "farm_event_id": event.id,
            "event_type": "STRAWBERRY_PICKING",
            "party_size": 4,
        }

    def test_a_booking_that_does_not_fit_records_nothing(
        self, client: TestClient, db_session: Session, customer: User, farm: Farm
    ) -> None:
        event = create_event(db_session, farm, capacity=3)

        response = client.post(
            "/api/event-reservations",
            json={"event_id": event.id, "party_size": 4},
            headers=auth_headers(customer),
        )

        assert response.status_code == 409
        assert events_of(db_session, ApplicationEventType.FARM_EVENT_BOOKED) == []


class TestInventory:
    def test_a_farmer_changing_stock_records_the_change(
        self, client: TestClient, db_session: Session, farmer: User, product: Product
    ) -> None:
        response = client.patch(
            f"/api/products/{product.id}/inventory",
            json={"quantity_available": 35},
            headers=auth_headers(farmer),
        )

        assert response.status_code == 200
        [event] = events_of(db_session, ApplicationEventType.INVENTORY_UPDATED)
        assert (event.user_id, event.farm_id, event.product_id) == (farmer.id, product.farm_id, product.id)
        assert event.event_metadata == {"previous_quantity": 20, "new_quantity": 35}

    def test_setting_the_stock_it_already_has_records_nothing(
        self, client: TestClient, db_session: Session, farmer: User, product: Product
    ) -> None:
        client.patch(
            f"/api/products/{product.id}/inventory",
            json={"quantity_available": 20},
            headers=auth_headers(farmer),
        )

        assert events_of(db_session, ApplicationEventType.INVENTORY_UPDATED) == []

    def test_another_farmer_cannot_create_an_inventory_event(
        self, client: TestClient, db_session: Session, product: Product
    ) -> None:
        other_farm = create_farmer_with_farm(db_session, "other@example.com")
        other_farmer = db_session.get(User, other_farm.owner_id)

        response = client.patch(
            f"/api/products/{product.id}/inventory",
            json={"quantity_available": 0},
            headers=auth_headers(other_farmer),
        )

        assert response.status_code == 403
        assert events_of(db_session, ApplicationEventType.INVENTORY_UPDATED) == []


class TestGrowOnDemand:
    def test_a_crop_request_is_recorded_without_its_location_or_notes(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        response = client.post(
            "/api/crop-requests",
            json=crop_request_payload(crop_name="sweet  corn", notes="Call me at 704-555-0199."),
            headers=auth_headers(customer),
        )

        assert response.status_code == 201
        [event] = events_of(db_session, ApplicationEventType.CROP_REQUESTED)
        assert (event.user_id, event.farm_id, event.product_id) == (customer.id, None, None)
        assert event.event_metadata == {
            "crop_request_id": response.json()["id"],
            "crop_name": "Sweet Corn",
            "quantity": 3,
            "unit": "LB",
            "frequency": "WEEKLY",
            "radius_miles": 25,
        }
        recorded = json.dumps(event.event_metadata)
        assert "704-555-0199" not in recorded
        assert "35.2271" not in recorded

    def test_a_duplicate_crop_request_records_nothing_more(
        self, client: TestClient, db_session: Session, customer: User
    ) -> None:
        first = client.post("/api/crop-requests", json=crop_request_payload(), headers=auth_headers(customer))
        second = client.post("/api/crop-requests", json=crop_request_payload(), headers=auth_headers(customer))

        assert (first.status_code, second.status_code) == (201, 409)
        assert len(events_of(db_session, ApplicationEventType.CROP_REQUESTED)) == 1

    def test_creating_a_grow_offer_records_it_for_the_farmer(
        self, client: TestClient, db_session: Session, farmer: User, farm: Farm
    ) -> None:
        response = client.post(
            "/api/grow-offers", json=grow_offer_payload(), headers=auth_headers(farmer)
        )

        assert response.status_code == 201
        [event] = events_of(db_session, ApplicationEventType.GROW_OFFER_CREATED)
        assert (event.user_id, event.farm_id) == (farmer.id, farm.id)
        assert event.event_metadata == {
            "grow_offer_id": response.json()["id"],
            "crop_name": "Okra",
            "expected_quantity": 100,
            "unit": "LB",
            "minimum_customers": 3,
        }

    def test_each_commitment_is_recorded_with_whether_it_confirmed_the_offer(
        self, client: TestClient, db_session: Session, farm: Farm
    ) -> None:
        offer = create_grow_offer(db_session, farm, minimum_customers=2)
        first = create_user(db_session, role=UserRole.CUSTOMER, email="first@example.com")
        second = create_user(db_session, role=UserRole.CUSTOMER, email="second@example.com")

        responses = [
            client.post(
                "/api/crop-commitments",
                json={"grow_offer_id": offer.id, "quantity": quantity},
                headers=auth_headers(customer),
            )
            for customer, quantity in ((first, 4), (second, 6))
        ]

        assert [response.status_code for response in responses] == [201, 201]
        events = events_of(db_session, ApplicationEventType.CROP_COMMITTED)
        assert [(event.user_id, event.farm_id) for event in events] == [(first.id, farm.id), (second.id, farm.id)]
        assert [event.event_metadata for event in events] == [
            {
                "crop_commitment_id": responses[0].json()["id"],
                "grow_offer_id": offer.id,
                "crop_name": "Okra",
                "quantity": 4,
                "confirmed_offer": False,
            },
            {
                "crop_commitment_id": responses[1].json()["id"],
                "grow_offer_id": offer.id,
                "crop_name": "Okra",
                "quantity": 6,
                "confirmed_offer": True,
            },
        ]

    def test_a_refused_commitment_records_nothing(
        self, client: TestClient, db_session: Session, customer: User, farm: Farm
    ) -> None:
        offer = create_grow_offer(db_session, farm, expected_quantity=10)

        response = client.post(
            "/api/crop-commitments",
            json={"grow_offer_id": offer.id, "quantity": 11},
            headers=auth_headers(customer),
        )

        assert response.status_code == 409
        assert events_of(db_session, ApplicationEventType.CROP_COMMITTED) == []


class TestDatabaseRules:
    def insert_raw_event(self, db_session: Session, event_type: str, metadata: str) -> None:
        db_session.execute(
            text("INSERT INTO application_events (event_type, metadata) VALUES (:event_type, CAST(:metadata AS jsonb))"),
            {"event_type": event_type, "metadata": metadata},
        )
        db_session.flush()

    def test_an_unknown_event_type_is_refused(self, db_session: Session) -> None:
        with pytest.raises(IntegrityError, match="ck_application_events_event_type_allowed"):
            self.insert_raw_event(db_session, "PAGE_SCROLLED", "{}")
        db_session.rollback()

    def test_metadata_must_be_an_object(self, db_session: Session) -> None:
        with pytest.raises(IntegrityError, match="ck_application_events_metadata_is_object"):
            self.insert_raw_event(db_session, "SEARCH_PERFORMED", "[]")
        db_session.rollback()

    def test_metadata_defaults_to_an_empty_object(self, db_session: Session) -> None:
        db_session.execute(text("INSERT INTO application_events (event_type) VALUES ('FARM_VIEWED')"))

        [event] = all_events(db_session)
        assert event.event_metadata == {}
        assert event.created_at is not None

    def test_deleting_a_product_keeps_its_events_without_the_link(
        self, db_session: Session, product: Product
    ) -> None:
        record_event(db_session, ApplicationEventType.PRODUCT_VIEWED, farm_id=product.farm_id, product_id=product.id)
        db_session.commit()

        db_session.delete(product)
        db_session.commit()

        [event] = all_events(db_session)
        db_session.refresh(event)
        assert event.product_id is None
        assert event.farm_id is not None
