"""The whole pipeline on real marketplace activity.

Farmers and customers use the browser-test backend's API, so every event is
recorded by the application's own code. The test then extracts a snapshot
of that database, validates it, runs `dbt build` (models, data tests and unit
tests) and checks the marts and the business questions against what it did.

It needs the browser-test backend running on a fresh, empty database:

    docker compose --profile e2e up -d --force-recreate --wait backend-e2e
    docker compose --profile pipeline run --rm -e POSTGRES_DB=farm2local_e2e \\
        -e PIPELINE_TEST_API_URL=http://backend-e2e:8000 pipeline python -m pytest

Raw files and the warehouse are written to a temporary directory.
"""

import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import duckdb
import psycopg
import pytest

from analytics.questions import answer_questions
from ingestion.config import SourceDatabase
from ingestion.datasets import DATASETS
from ingestion.extract import extract_snapshot, open_snapshot_connection
from ingestion.storage import RawStorage
from ingestion.validate import validate_snapshot

API_URL = os.environ.get("PIPELINE_TEST_API_URL")
DBT_DIRECTORY = Path(__file__).resolve().parents[1] / "dbt"
PASSWORD = "pipeline-test-password"

pytestmark = pytest.mark.skipif(
    not API_URL, reason="Set PIPELINE_TEST_API_URL to the browser-test backend to run the end-to-end pipeline test"
)

# Where people are. Farms are public listings; the customer points are where
# they search from and must never appear in the raw files.
ASHEVILLE_FARM = (35.5951, -82.5515)
CHARLOTTE_FARM = (35.2271, -80.8431)
ASHEVILLE_CUSTOMER = (35.598, -82.555)
CHARLOTTE_CUSTOMER = (35.23, -80.84)


def marketplace_today() -> date:
    return datetime.now(ZoneInfo(os.environ.get("MARKETPLACE_TIMEZONE", "America/New_York"))).date()


class MarketplaceApi:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.email_number = 0

    def call(self, method: str, path: str, body: Any = None, token: str | None = None) -> Any:
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                content = response.read()
        except urllib.error.HTTPError as error:
            raise AssertionError(f"{method} {path} returned {error.code}: {error.read().decode()}") from None
        return json.loads(content) if content else None

    def sign_up(self, name: str, role: str) -> str:
        self.email_number += 1
        email = f"pipeline-{role.lower()}-{self.email_number}@example.com"
        self.call("POST", "/api/auth/register", {"name": name, "email": email, "password": PASSWORD, "role": role})
        return self.call("POST", "/api/auth/login", {"email": email, "password": PASSWORD})["access_token"]

    def create_farm(self, token: str, name: str, city: str, location: tuple[float, float]) -> dict[str, Any]:
        latitude, longitude = location
        return self.call(
            "POST",
            "/api/farms",
            {
                "farm_name": name, "description": None, "address": "1 Field Road", "city": city,
                "state": "NC", "zip_code": "28801", "latitude": latitude, "longitude": longitude,
                "phone": "828-555-0100", "pickup_available": True, "delivery_available": False,
            },
            token,
        )

    def create_product(self, token: str, name: str, price: str, unit: str, quantity: int) -> dict[str, Any]:
        return self.call(
            "POST",
            "/api/products",
            {
                "name": name, "category": "VEGETABLES", "description": None, "price": price,
                "unit": unit, "quantity_available": quantity, "harvest_date": None,
                "available_from": None, "available_until": None, "organic": False, "active": True,
            },
            token,
        )

    def search(self, location: tuple[float, float], query: str | None = None) -> list[dict[str, Any]]:
        latitude, longitude = location
        path = f"/api/products/search?latitude={latitude}&longitude={longitude}"
        if query:
            path += f"&query={urllib.request.quote(query)}"
        return self.call("GET", path)

    def reserve(self, token: str, product_id: int, quantity: int) -> dict[str, Any]:
        pickup_date = (marketplace_today() + timedelta(days=1)).isoformat()
        return self.call(
            "POST",
            "/api/reservations",
            {"product_id": product_id, "quantity": quantity, "pickup_date": pickup_date, "pickup_time": "10:00:00"},
            token,
        )

    def request_crop(self, token: str, crop_name: str, quantity: int, location: tuple[float, float]) -> None:
        latitude, longitude = location
        self.call(
            "POST",
            "/api/crop-requests",
            {
                "crop_name": crop_name, "quantity": quantity, "unit": "LB", "frequency": "WEEKLY",
                "latitude": latitude, "longitude": longitude, "radius_miles": 25,
                "preferred_season": None, "notes": "Leave at the side gate, code 4417.",
            },
            token,
        )

    def offer_to_grow(self, token: str, crop_name: str, minimum_customers: int) -> dict[str, Any]:
        today = marketplace_today()
        return self.call(
            "POST",
            "/api/grow-offers",
            {
                "crop_name": crop_name, "expected_quantity": 40, "unit": "LB", "estimated_price": "3.50",
                "planting_date": (today + timedelta(days=14)).isoformat(),
                "expected_harvest_date": (today + timedelta(days=90)).isoformat(),
                "minimum_customers": minimum_customers,
            },
            token,
        )


@dataclass(frozen=True)
class PipelineRun:
    snapshot_date: date
    storage: RawStorage
    warehouse: duckdb.DuckDBPyConnection


def use_the_marketplace(api: MarketplaceApi) -> None:
    """A small day of marketplace activity whose analytics are known in advance."""
    farmer_a = api.sign_up("Avery Riverbend", "FARMER")
    farmer_b = api.sign_up("Blake Queen", "FARMER")
    customer_1 = api.sign_up("Casey Asheville", "CUSTOMER")
    customer_2 = api.sign_up("Dana Charlotte", "CUSTOMER")

    riverbend = api.create_farm(farmer_a, "Riverbend Farm", "Asheville", ASHEVILLE_FARM)
    api.create_farm(farmer_b, "Queen City Growers", "Charlotte", CHARLOTTE_FARM)
    tomatoes = api.create_product(farmer_a, "Heirloom Tomatoes", "4.50", "LB", 20)
    chard = api.create_product(farmer_a, "Rainbow Chard", "3.00", "BUNCH", 10)
    corn = api.create_product(farmer_b, "Sweet Corn", "1.00", "EACH", 50)
    event = api.call(
        "POST",
        "/api/events",
        {
            "title": "Corn Maze Morning", "description": None, "event_type": "FARM_TOUR",
            "event_date": (marketplace_today() + timedelta(days=7)).isoformat(),
            "start_time": "09:00:00", "end_time": "11:00:00", "price": "12.00", "capacity": 20,
        },
        farmer_b,
    )

    # Searching: tomatoes are found near Asheville, okra is found nowhere.
    assert len(api.search(ASHEVILLE_CUSTOMER, "tomatoes")) == 1
    assert api.search(ASHEVILLE_CUSTOMER, "okra") == []
    assert api.search(ASHEVILLE_CUSTOMER, "Okra") == []
    assert api.search(CHARLOTTE_CUSTOMER, "okra") == []
    assert [result["product"]["name"] for result in api.search(CHARLOTTE_CUSTOMER)] == ["Sweet Corn"]
    api.call("GET", f"/api/farms/{riverbend['id']}")

    # Reserving, cancelling, restocking and booking.
    api.reserve(customer_1, tomatoes["id"], 3)
    cancelled = api.reserve(customer_2, corn["id"], 5)
    api.call("PATCH", f"/api/reservations/{cancelled['id']}/status", {"status": "CANCELLED"}, customer_2)
    api.reserve(customer_2, corn["id"], 10)
    api.call("PATCH", f"/api/products/{chard['id']}/inventory", {"quantity_available": 15}, farmer_a)
    api.call("POST", "/api/event-reservations", {"event_id": event["id"], "party_size": 2}, customer_1)

    # Grow-On-Demand: both customers want okra, one also wants purple kale.
    api.request_crop(customer_1, "Okra", 2, ASHEVILLE_CUSTOMER)
    api.request_crop(customer_2, "okra", 3, CHARLOTTE_CUSTOMER)
    api.request_crop(customer_2, "Purple Kale", 1, CHARLOTTE_CUSTOMER)
    okra_offer = api.offer_to_grow(farmer_b, "Okra", minimum_customers=1)
    api.offer_to_grow(farmer_a, "Purple Kale", minimum_customers=3)
    commitment = api.call("POST", "/api/crop-commitments", {"grow_offer_id": okra_offer["id"], "quantity": 3}, customer_2)
    assert commitment["offer"]["status"] == "CONFIRMED"


def build_marts(storage_root: Path, warehouse_path: Path, target_path: Path, snapshot_date: date) -> None:
    result = subprocess.run(
        [
            "dbt", "build",
            "--project-dir", str(DBT_DIRECTORY),
            "--profiles-dir", str(DBT_DIRECTORY),
            "--target-path", str(target_path),
            "--vars", json.dumps({"snapshot_date": snapshot_date.isoformat()}),
        ],
        env=os.environ | {"RAW_DATA_URI": str(storage_root), "DUCKDB_PATH": str(warehouse_path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="module")
def pipeline_run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[PipelineRun]:
    source = SourceDatabase.from_environment()
    assert source.name.endswith("_e2e"), "The end-to-end test writes through the API; use the e2e database"
    with source.connect() as connection:
        farm_count = connection.execute("SELECT count(*) FROM farms").fetchone()[0]
    if farm_count:
        pytest.fail(
            "The e2e database already has data. Recreate it first: "
            "docker compose --profile e2e up -d --force-recreate --wait backend-e2e"
        )

    use_the_marketplace(MarketplaceApi(API_URL))

    root = tmp_path_factory.mktemp("pipeline")
    storage_root = root / "raw"
    storage = RawStorage.from_uri(str(storage_root))
    snapshot_date = datetime.now(UTC).date()
    extract_snapshot(source, storage, snapshot_date)
    assert validate_snapshot(storage, snapshot_date) == []
    build_marts(storage_root, root / "warehouse.duckdb", root / "dbt-target", snapshot_date)

    warehouse = duckdb.connect(str(root / "warehouse.duckdb"), read_only=True)
    yield PipelineRun(snapshot_date, storage, warehouse)
    warehouse.close()


def rows(run: PipelineRun, query: str) -> list[tuple[Any, ...]]:
    return run.warehouse.execute(query).fetchall()


def days_observed(run: PipelineRun) -> int:
    """Stock is counted from the first change's marketplace day to the snapshot's UTC day."""
    return (run.snapshot_date - marketplace_today()).days + 1


class TestEvents:
    def test_every_action_was_recorded_once(self, pipeline_run: PipelineRun) -> None:
        counts = dict(rows(pipeline_run, "select event_type, count(*) from stg_events group by 1"))

        assert counts == {
            "SEARCH_PERFORMED": 5,
            "NO_SEARCH_RESULT": 3,
            "PRODUCT_VIEWED": 2,
            "FARM_VIEWED": 3,
            "RESERVATION_CREATED": 3,
            "INVENTORY_UPDATED": 1,
            "FARM_EVENT_BOOKED": 1,
            "CROP_REQUESTED": 3,
            "GROW_OFFER_CREATED": 2,
            "CROP_COMMITTED": 1,
        }

    def test_browsing_events_carry_no_user(self, pipeline_run: PipelineRun) -> None:
        users = rows(
            pipeline_run,
            """
            select distinct user_id from stg_events
            where event_type in ('SEARCH_PERFORMED', 'NO_SEARCH_RESULT', 'PRODUCT_VIEWED', 'FARM_VIEWED')
            """,
        )

        assert users == [(None,)]


class TestRawFiles:
    def test_no_personal_details_or_exact_customer_locations_leave_the_database(self, pipeline_run: PipelineRun) -> None:
        tables = {
            dataset.name: pipeline_run.storage.read_table(
                pipeline_run.storage.dataset_path(dataset.name, pipeline_run.snapshot_date)
            )
            for dataset in DATASETS
        }
        everything = json.dumps({name: table.to_pylist() for name, table in tables.items()}, default=str)

        for private_value in ("35.598", "82.555", "35.23,", "80.84,", "side gate", "828-555-0100", "1 Field Road", "@example.com"):
            assert private_value not in everything
        assert not {"latitude", "longitude", "notes"} & set(tables["crop_requests"].column_names)
        assert not {"latitude", "longitude", "address", "phone"} & set(tables["farms"].column_names)

    def test_extracting_the_same_date_again_gives_the_same_snapshot(
        self, pipeline_run: PipelineRun, tmp_path: Path
    ) -> None:
        again = RawStorage.from_uri(str(tmp_path / "raw"))

        extract_snapshot(SourceDatabase.from_environment(), again, pipeline_run.snapshot_date)

        for dataset in DATASETS:
            first = pipeline_run.storage.read_table(pipeline_run.storage.dataset_path(dataset.name, pipeline_run.snapshot_date))
            second = again.read_table(again.dataset_path(dataset.name, pipeline_run.snapshot_date))
            assert second.equals(first), dataset.name

    def test_the_extract_cannot_change_the_application_database(self, pipeline_run: PipelineRun) -> None:
        with open_snapshot_connection(SourceDatabase.from_environment()) as connection:
            with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
                connection.execute("INSERT INTO application_events (event_type) VALUES ('FARM_VIEWED')")


class TestMarts:
    def test_crop_demand_combines_searches_requests_and_supply(self, pipeline_run: PipelineRun) -> None:
        crops = rows(
            pipeline_run,
            """
            select crop_name, searches, no_result_searches, open_requests, unmet_requests,
                   customers_waiting, active_grow_offers, listings_available, unmet_demand_signals
            from mart_unfulfilled_crop_demand order by crop_name
            """,
        )

        assert crops == [
            # Customer 2's okra request is met by the okra offer they joined; customer 1's is not.
            ("Okra", 3, 3, 2, 1, 1, 1, 0, 4),
            ("Purple Kale", 0, 0, 1, 1, 1, 1, 0, 1),
            ("Tomatoes", 1, 0, 0, 0, 0, 0, 1, 0),
        ]

    def test_demand_is_placed_in_coarse_regions(self, pipeline_run: PipelineRun) -> None:
        regions = rows(
            pipeline_run,
            """
            select region_id, searches, no_result_searches, open_requests, unmet_requests,
                   farms, listings_available, unmet_demand_signals
            from mart_demand_by_region order by region_id
            """,
        )

        assert regions == [
            ("35.2,-80.8", 2, 1, 2, 1, 1, 1, 2),
            ("35.6,-82.6", 3, 2, 1, 1, 1, 2, 3),
        ]

    def test_inventory_turnover_compares_sales_with_average_stock(self, pipeline_run: PipelineRun) -> None:
        days = days_observed(pipeline_run)
        turnover = rows(
            pipeline_run,
            """
            select farm_name, days_observed, average_stock_value, units_sold, sold_value,
                   inventory_turnover, days_of_inventory
            from mart_inventory_turnover order by farm_name
            """,
        )

        # Queen City: 40 ears left at $1, ten sold (the cancelled five returned).
        # Riverbend: 17 lb of tomatoes at $4.50 and 15 bunches of chard at $3.
        assert [tuple(float(value) if not isinstance(value, str) else value for value in row) for row in turnover] == [
            ("Queen City Growers", days, 40.0, 10.0, 10.0, 0.25, 4.0 * days),
            ("Riverbend Farm", days, 121.5, 3.0, 13.5, 0.1111, 9.0 * days),
        ]

    def test_commitment_conversion_shows_which_offers_reached_their_minimum(self, pipeline_run: PipelineRun) -> None:
        offers = rows(
            pipeline_run,
            """
            select crop_name, status, committed_customers, reached_minimum,
                   minimum_reached_at is not null, customers_who_requested_first
            from mart_crop_commitment_conversion order by crop_name
            """,
        )

        assert offers == [
            ("Okra", "CONFIRMED", 1, True, True, 1),
            ("Purple Kale", "OPEN", 0, False, False, 0),
        ]

    def test_product_demand_counts_views_and_reservations(self, pipeline_run: PipelineRun) -> None:
        demand = rows(
            pipeline_run,
            """
            select product_name, sum(product_views), sum(reservations), sum(units_reserved), sum(cancelled_reservations)
            from mart_daily_product_demand group by 1 order by 1
            """,
        )

        assert demand == [("Heirloom Tomatoes", 1, 1, 3, 0), ("Sweet Corn", 1, 2, 15, 1)]

    def test_reservations_cover_products_and_farm_experiences(self, pipeline_run: PipelineRun) -> None:
        reservations = rows(
            pipeline_run,
            """
            select reservation_type, quantity, status, estimated_value, lead_time_days
            from mart_reservations order by reservation_type, reservation_id
            """,
        )

        assert [(kind, quantity, status, float(value)) for kind, quantity, status, value, _ in reservations] == [
            ("EVENT", 2, "PENDING", 24.0),
            ("PRODUCT", 3, "PENDING", 13.5),
            ("PRODUCT", 5, "CANCELLED", 5.0),
            ("PRODUCT", 10, "PENDING", 10.0),
        ]
        assert [lead_time for *_, lead_time in reservations] == [7, 1, 1, 1]


def test_the_business_questions_are_answered(pipeline_run: PipelineRun) -> None:
    answers = {answer.question.title: answer.rows for answer in answer_questions(pipeline_run.warehouse)}

    assert answers["Which crops are most searched?"][0][:2] == ("Okra", 3)
    assert answers["Which crops frequently return no results?"][0][:2] == ("Okra", 3)
    assert answers["Which regions show the highest unmet demand?"][0][:2] == ("35.6,-82.6", 3)
    assert answers["Which farms have the fastest inventory turnover?"][0][0] == "Queen City Growers"
    assert answers["What percentage of Grow Offers reach commitment?"] == [(2, 1, 50.0)]
    assert answers["What crops show strong demand but low supply?"][0][:2] == ("Okra", 4.0)
