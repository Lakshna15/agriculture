"""The tables the pipeline copies out of the application database, and their exact shape.

Each dataset selects only the columns analytics needs. In particular:

- No names, emails, password hashes, phone numbers, street addresses or
  free-text notes are extracted.
- Locations leave the database only as a region: latitude and longitude
  rounded to one decimal place, a cell about 7 miles across. A customer's
  exact position never reaches a raw file.

Every query takes a %(cutoff)s parameter and keeps only rows created before
it, so re-running a snapshot date selects the same rows.
"""

from dataclasses import dataclass

import pyarrow as pa

ID = pa.int64()
TEXT = pa.string()
INTEGER = pa.int64()
FLAG = pa.bool_()
DAY = pa.date32()
MONEY = pa.decimal128(10, 2)
DEGREES = pa.float64()
TIMESTAMP = pa.timestamp("us", tz="UTC")


@dataclass(frozen=True)
class Dataset:
    name: str
    query: str
    schema: pa.Schema
    primary_key: str
    # The column the snapshot cutoff applies to.
    created_column: str


def _schema(*columns: tuple[str, pa.DataType]) -> pa.Schema:
    return pa.schema([pa.field(name, data_type) for name, data_type in columns])


def _region(column: str, alias: str) -> str:
    return f"round({column}::numeric, 1)::double precision AS {alias}"


DATASETS: tuple[Dataset, ...] = (
    Dataset(
        name="application_events",
        query="""
            SELECT id, event_type, user_id, farm_id, product_id, metadata::text AS metadata, created_at
            FROM application_events
            WHERE created_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("event_type", TEXT),
            ("user_id", ID),
            ("farm_id", ID),
            ("product_id", ID),
            ("metadata", TEXT),
            ("created_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="created_at",
    ),
    Dataset(
        name="farms",
        query=f"""
            SELECT id, owner_id, farm_name, city, state,
                   {_region("latitude", "region_latitude")},
                   {_region("longitude", "region_longitude")},
                   pickup_available, delivery_available, created_at
            FROM farms
            WHERE created_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("owner_id", ID),
            ("farm_name", TEXT),
            ("city", TEXT),
            ("state", TEXT),
            ("region_latitude", DEGREES),
            ("region_longitude", DEGREES),
            ("pickup_available", FLAG),
            ("delivery_available", FLAG),
            ("created_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="created_at",
    ),
    Dataset(
        name="products",
        query="""
            SELECT id, farm_id, name, category, unit, price, quantity_available, organic, active,
                   harvest_date, available_from, available_until, created_at, updated_at
            FROM products
            WHERE created_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("farm_id", ID),
            ("name", TEXT),
            ("category", TEXT),
            ("unit", TEXT),
            ("price", MONEY),
            ("quantity_available", INTEGER),
            ("organic", FLAG),
            ("active", FLAG),
            ("harvest_date", DAY),
            ("available_from", DAY),
            ("available_until", DAY),
            ("created_at", TIMESTAMP),
            ("updated_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="created_at",
    ),
    Dataset(
        name="inventory_history",
        query="""
            SELECT id, product_id, previous_quantity, new_quantity, changed_at
            FROM inventory_history
            WHERE changed_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("product_id", ID),
            ("previous_quantity", INTEGER),
            ("new_quantity", INTEGER),
            ("changed_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="changed_at",
    ),
    Dataset(
        name="product_reservations",
        query="""
            SELECT id, customer_id, product_id, quantity, pickup_date, status, created_at, updated_at
            FROM product_reservations
            WHERE created_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("customer_id", ID),
            ("product_id", ID),
            ("quantity", INTEGER),
            ("pickup_date", DAY),
            ("status", TEXT),
            ("created_at", TIMESTAMP),
            ("updated_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="created_at",
    ),
    Dataset(
        name="farm_events",
        query="""
            SELECT id, farm_id, event_type, event_date, price, capacity, created_at
            FROM farm_events
            WHERE created_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("farm_id", ID),
            ("event_type", TEXT),
            ("event_date", DAY),
            ("price", MONEY),
            ("capacity", INTEGER),
            ("created_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="created_at",
    ),
    Dataset(
        name="event_reservations",
        query="""
            SELECT id, event_id, customer_id, party_size, status, created_at
            FROM event_reservations
            WHERE created_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("event_id", ID),
            ("customer_id", ID),
            ("party_size", INTEGER),
            ("status", TEXT),
            ("created_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="created_at",
    ),
    Dataset(
        name="crop_requests",
        query=f"""
            SELECT id, customer_id, crop_name, quantity, unit, frequency, radius_miles,
                   preferred_season, status,
                   {_region("latitude", "region_latitude")},
                   {_region("longitude", "region_longitude")},
                   created_at
            FROM crop_requests
            WHERE created_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("customer_id", ID),
            ("crop_name", TEXT),
            ("quantity", INTEGER),
            ("unit", TEXT),
            ("frequency", TEXT),
            ("radius_miles", INTEGER),
            ("preferred_season", TEXT),
            ("status", TEXT),
            ("region_latitude", DEGREES),
            ("region_longitude", DEGREES),
            ("created_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="created_at",
    ),
    Dataset(
        name="grow_offers",
        query="""
            SELECT id, farm_id, crop_name, expected_quantity, unit, estimated_price,
                   planting_date, expected_harvest_date, minimum_customers, status, created_at
            FROM grow_offers
            WHERE created_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("farm_id", ID),
            ("crop_name", TEXT),
            ("expected_quantity", INTEGER),
            ("unit", TEXT),
            ("estimated_price", MONEY),
            ("planting_date", DAY),
            ("expected_harvest_date", DAY),
            ("minimum_customers", INTEGER),
            ("status", TEXT),
            ("created_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="created_at",
    ),
    Dataset(
        name="crop_commitments",
        query="""
            SELECT id, grow_offer_id, customer_id, quantity, created_at
            FROM crop_commitments
            WHERE created_at < %(cutoff)s
            ORDER BY id
        """,
        schema=_schema(
            ("id", ID),
            ("grow_offer_id", ID),
            ("customer_id", ID),
            ("quantity", INTEGER),
            ("created_at", TIMESTAMP),
        ),
        primary_key="id",
        created_column="created_at",
    ),
)

DATASETS_BY_NAME = {dataset.name: dataset for dataset in DATASETS}
