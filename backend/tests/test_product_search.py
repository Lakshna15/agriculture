"""Search tests use fixed coordinates so that every distance is known in advance.

Searches start in uptown Charlotte, North Carolina. Farms are placed due north
of that point, where distance depends only on latitude: one degree of latitude
there spans about 68.94 miles.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.user import User
from app.services.clock import marketplace_today
from tests.helpers import auth_headers, create_farmer_with_farm, create_product, farm_payload

SEARCH_URL = "/api/products/search"

ORIGIN_LATITUDE = 35.2271
ORIGIN_LONGITUDE = -80.8431
MILES_PER_DEGREE_OF_LATITUDE = 68.94
# At the origin's latitude a degree of longitude is shorter than a degree of latitude.
MILES_PER_DEGREE_OF_LONGITUDE = 56.57


def farm_miles_north(db_session: Session, miles: float, farm_name: str) -> Farm:
    """A farm the given distance due north of the search origin."""
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


def farm_names(results: list[dict[str, Any]]) -> list[str]:
    return [result["farm"]["farm_name"] for result in results]


def product_names(results: list[dict[str, Any]]) -> list[str]:
    return [result["product"]["name"] for result in results]


@pytest.fixture
def farms_at_known_distances(db_session: Session) -> None:
    """Farms 3, 4.5, 5.5, 20, 24, 26 and 40 miles from the origin, one product each."""
    for miles in (3, 4.5, 5.5, 20, 24, 26, 40):
        farm = farm_miles_north(db_session, miles, f"Farm {miles} mi")
        create_product(db_session, farm, name=f"Tomatoes from {miles} mi")


class TestRadiusFiltering:
    def test_five_mile_radius_returns_only_farms_within_five_miles(
        self, client: TestClient, farms_at_known_distances: None
    ) -> None:
        results = search(client, radius_miles=5)

        assert farm_names(results) == ["Farm 3 mi", "Farm 4.5 mi"]

    def test_twenty_five_mile_radius_returns_only_farms_within_twenty_five_miles(
        self, client: TestClient, farms_at_known_distances: None
    ) -> None:
        results = search(client, radius_miles=25)

        assert farm_names(results) == [
            "Farm 3 mi",
            "Farm 4.5 mi",
            "Farm 5.5 mi",
            "Farm 20 mi",
            "Farm 24 mi",
        ]

    def test_radius_defaults_to_twenty_five_miles(
        self, client: TestClient, farms_at_known_distances: None
    ) -> None:
        assert len(search(client)) == 5

    def test_larger_radius_reaches_the_farthest_farm(
        self, client: TestClient, farms_at_known_distances: None
    ) -> None:
        assert len(search(client, radius_miles=50)) == 7

    def test_no_farm_in_range_returns_an_empty_list(
        self, client: TestClient, farms_at_known_distances: None
    ) -> None:
        assert search(client, radius_miles=1) == []


class TestDistance:
    def test_reported_distance_matches_the_known_distance(
        self, client: TestClient, farms_at_known_distances: None
    ) -> None:
        results = search(client, radius_miles=50)

        distances = {result["farm"]["farm_name"]: result["distance_miles"] for result in results}
        assert distances["Farm 3 mi"] == pytest.approx(3, abs=0.05)
        assert distances["Farm 20 mi"] == pytest.approx(20, abs=0.05)
        assert distances["Farm 40 mi"] == pytest.approx(40, abs=0.05)

    def test_distance_is_measured_east_west_as_well_as_north_south(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Swapping latitude and longitude anywhere in the query would put this
        # farm thousands of miles away instead of ten.
        farm = create_farmer_with_farm(
            db_session,
            "west@example.com",
            farm_name="West Farm",
            latitude=ORIGIN_LATITUDE,
            longitude=ORIGIN_LONGITUDE - 10 / MILES_PER_DEGREE_OF_LONGITUDE,
        )
        create_product(db_session, farm)

        results = search(client, radius_miles=25)

        assert farm_names(results) == ["West Farm"]
        assert results[0]["distance_miles"] == pytest.approx(10, abs=0.05)

    def test_a_farm_at_the_search_point_is_zero_miles_away(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_product(db_session, farm_miles_north(db_session, 0, "Right Here Farm"))

        results = search(client, radius_miles=5)

        assert results[0]["distance_miles"] == 0

    def test_search_follows_a_farm_whose_coordinates_are_edited(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Moving Farm")
        create_product(db_session, farm)
        owner = db_session.get(User, farm.owner_id)
        assert owner is not None
        assert len(search(client, radius_miles=5)) == 1

        # The location column is generated by the database, so editing the
        # coordinates through the API is all it takes to move the farm.
        response = client.put(
            f"/api/farms/{farm.id}",
            json=farm_payload(
                farm_name="Moving Farm",
                latitude=ORIGIN_LATITUDE + 30 / MILES_PER_DEGREE_OF_LATITUDE,
                longitude=ORIGIN_LONGITUDE,
            ),
            headers=auth_headers(owner),
        )
        assert response.status_code == 200

        assert search(client, radius_miles=5) == []
        [result] = search(client, radius_miles=50)
        assert result["distance_miles"] == pytest.approx(30, abs=0.05)


class TestSorting:
    def test_results_are_sorted_by_distance_by_default(
        self, client: TestClient, db_session: Session
    ) -> None:
        for miles in (18, 2, 9):
            create_product(db_session, farm_miles_north(db_session, miles, f"Farm {miles} mi"))

        results = search(client, radius_miles=25)

        assert farm_names(results) == ["Farm 2 mi", "Farm 9 mi", "Farm 18 mi"]
        distances = [result["distance_miles"] for result in results]
        assert distances == sorted(distances)

    def test_explicit_distance_sort_is_nearest_first(
        self, client: TestClient, db_session: Session
    ) -> None:
        for miles in (18, 2, 9):
            create_product(db_session, farm_miles_north(db_session, miles, f"Farm {miles} mi"))

        results = search(client, radius_miles=25, sort="distance")

        assert farm_names(results) == ["Farm 2 mi", "Farm 9 mi", "Farm 18 mi"]

    def test_price_sort_is_cheapest_first(self, client: TestClient, db_session: Session) -> None:
        near_farm = farm_miles_north(db_session, 2, "Near Farm")
        far_farm = farm_miles_north(db_session, 15, "Far Farm")
        create_product(db_session, near_farm, name="Premium Tomatoes", price="10.00")
        create_product(db_session, near_farm, name="Standard Tomatoes", price="5.00")
        create_product(db_session, far_farm, name="Bargain Tomatoes", price="2.50")

        results = search(client, radius_miles=25, sort="price")

        assert product_names(results) == ["Bargain Tomatoes", "Standard Tomatoes", "Premium Tomatoes"]
        assert [result["price"] for result in results] == ["2.50", "5.00", "10.00"]

    def test_equal_prices_fall_back_to_distance(
        self, client: TestClient, db_session: Session
    ) -> None:
        create_product(db_session, farm_miles_north(db_session, 15, "Far Farm"), price="3.00")
        create_product(db_session, farm_miles_north(db_session, 2, "Near Farm"), price="3.00")

        results = search(client, radius_miles=25, sort="price")

        assert farm_names(results) == ["Near Farm", "Far Farm"]

    def test_harvest_date_sort_is_most_recent_first_with_undated_last(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 2, "Near Farm")
        create_product(db_session, farm, name="Picked Last Week", harvest_date=date(2026, 6, 1))
        create_product(db_session, farm, name="No Harvest Date", harvest_date=None)
        create_product(db_session, farm, name="Picked Yesterday", harvest_date=date(2026, 6, 7))

        results = search(client, radius_miles=5, sort="harvest_date")

        assert product_names(results) == ["Picked Yesterday", "Picked Last Week", "No Harvest Date"]
        assert [result["harvest_date"] for result in results] == ["2026-06-07", "2026-06-01", None]


class TestAvailabilityFiltering:
    @pytest.fixture
    def products_with_varied_availability(self, db_session: Session) -> None:
        today = marketplace_today()
        farm = farm_miles_north(db_session, 2, "Near Farm")
        create_product(db_session, farm, name="In Stock")
        create_product(
            db_session,
            farm,
            name="In Season Now",
            available_from=today - timedelta(days=5),
            available_until=today + timedelta(days=5),
        )
        create_product(
            db_session, farm, name="Last Day Today", available_from=today, available_until=today
        )
        create_product(db_session, farm, name="Sold Out", quantity_available=0)
        create_product(
            db_session, farm, name="Not Yet In Season", available_from=today + timedelta(days=3)
        )
        create_product(
            db_session, farm, name="Season Over", available_until=today - timedelta(days=1)
        )
        create_product(db_session, farm, name="Withdrawn", active=False)

    def test_only_available_products_are_returned_by_default(
        self, client: TestClient, products_with_varied_availability: None
    ) -> None:
        results = search(client, radius_miles=5)

        assert sorted(product_names(results)) == ["In Season Now", "In Stock", "Last Day Today"]

    def test_available_only_true_matches_the_default(
        self, client: TestClient, products_with_varied_availability: None
    ) -> None:
        results = search(client, radius_miles=5, available_only="true")

        assert sorted(product_names(results)) == ["In Season Now", "In Stock", "Last Day Today"]

    def test_turning_the_filter_off_includes_unavailable_but_never_inactive_products(
        self, client: TestClient, products_with_varied_availability: None
    ) -> None:
        results = search(client, radius_miles=5, available_only="false")

        assert sorted(product_names(results)) == [
            "In Season Now",
            "In Stock",
            "Last Day Today",
            "Not Yet In Season",
            "Season Over",
            "Sold Out",
        ]

    def test_sold_out_product_reports_zero_quantity(
        self, client: TestClient, products_with_varied_availability: None
    ) -> None:
        results = search(client, radius_miles=5, available_only="false", query="Sold Out")

        assert results[0]["quantity_available"] == 0


class TestTextAndCategoryFilters:
    @pytest.fixture
    def mixed_products(self, db_session: Session) -> None:
        farm = farm_miles_north(db_session, 2, "Near Farm")
        create_product(db_session, farm, name="Heirloom Tomatoes", category="VEGETABLES")
        create_product(db_session, farm, name="Cherry Tomatoes", category="VEGETABLES")
        create_product(db_session, farm, name="Strawberries", category="FRUITS")
        create_product(db_session, farm, name="Free-Range Eggs", category="EGGS")
        create_product(db_session, farm, name="100% Grass-Fed Beef", category="MEAT")

    def test_query_matches_part_of_the_name_ignoring_case(
        self, client: TestClient, mixed_products: None
    ) -> None:
        results = search(client, radius_miles=5, query="TOMATO")

        assert sorted(product_names(results)) == ["Cherry Tomatoes", "Heirloom Tomatoes"]

    def test_query_with_no_match_returns_nothing(
        self, client: TestClient, mixed_products: None
    ) -> None:
        assert search(client, radius_miles=5, query="okra") == []

    def test_blank_query_is_treated_as_no_query(
        self, client: TestClient, mixed_products: None
    ) -> None:
        assert len(search(client, radius_miles=5, query="   ")) == 5

    def test_wildcard_characters_in_the_query_are_matched_literally(
        self, client: TestClient, mixed_products: None
    ) -> None:
        # Unescaped, "%" would match every product and "_" any single character.
        assert product_names(search(client, radius_miles=5, query="100%")) == ["100% Grass-Fed Beef"]
        assert product_names(search(client, radius_miles=5, query="%")) == ["100% Grass-Fed Beef"]
        assert search(client, radius_miles=5, query="_") == []

    def test_category_filter_returns_only_that_category(
        self, client: TestClient, mixed_products: None
    ) -> None:
        results = search(client, radius_miles=5, category="FRUITS")

        assert product_names(results) == ["Strawberries"]

    def test_query_and_category_combine(self, client: TestClient, mixed_products: None) -> None:
        assert search(client, radius_miles=5, query="tomato", category="FRUITS") == []


class TestSearchContract:
    def test_each_result_has_the_documented_shape(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        product = create_product(
            db_session, farm, price="4.50", quantity_available=12, harvest_date=date(2026, 6, 1)
        )

        [result] = search(client, radius_miles=5)

        assert set(result) == {
            "product",
            "farm",
            "distance_miles",
            "price",
            "quantity_available",
            "harvest_date",
        }
        assert result["product"]["id"] == product.id
        assert result["product"]["name"] == "Heirloom Tomatoes"
        assert result["product"]["category"] == "VEGETABLES"
        assert result["product"]["unit"] == "LB"
        assert result["product"]["organic"] is True
        assert result["farm"] == {
            "id": farm.id,
            "farm_name": "Near Farm",
            "city": "Charlotte",
            "state": "NC",
            "pickup_available": True,
            "delivery_available": False,
        }
        assert result["price"] == "4.50"
        assert result["quantity_available"] == 12
        assert result["harvest_date"] == "2026-06-01"

    def test_search_needs_no_account(self, client: TestClient, db_session: Session) -> None:
        create_product(db_session, farm_miles_north(db_session, 3, "Near Farm"))

        response = client.get(
            SEARCH_URL, params={"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE}
        )

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_limit_caps_the_number_of_results(
        self, client: TestClient, db_session: Session
    ) -> None:
        farm = farm_miles_north(db_session, 3, "Near Farm")
        for number in range(4):
            create_product(db_session, farm, name=f"Product {number}")

        assert len(search(client, radius_miles=5, limit=2)) == 2

    @pytest.mark.parametrize(
        "params",
        [
            {"longitude": ORIGIN_LONGITUDE},
            {"latitude": ORIGIN_LATITUDE},
            {"latitude": 91, "longitude": ORIGIN_LONGITUDE},
            {"latitude": ORIGIN_LATITUDE, "longitude": -181},
            {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE, "radius_miles": 0},
            {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE, "radius_miles": -5},
            {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE, "radius_miles": 501},
            {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE, "sort": "popularity"},
            {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE, "category": "FURNITURE"},
            {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE, "limit": 0},
            {"latitude": ORIGIN_LATITUDE, "longitude": ORIGIN_LONGITUDE, "limit": 101},
        ],
        ids=[
            "missing latitude",
            "missing longitude",
            "latitude out of range",
            "longitude out of range",
            "zero radius",
            "negative radius",
            "radius too large",
            "unknown sort",
            "unknown category",
            "zero limit",
            "limit too large",
        ],
    )
    def test_invalid_parameters_are_rejected(
        self, client: TestClient, params: dict[str, Any]
    ) -> None:
        response = client.get(SEARCH_URL, params=params)

        assert response.status_code == 422
