from datetime import UTC, date, datetime
from decimal import Decimal

import pyarrow as pa

from ingestion.datasets import DATASETS_BY_NAME
from ingestion.extract import to_record_batch
from ingestion.snapshots import parse_snapshot_date, snapshot_cutoff


def test_a_snapshot_holds_everything_created_before_the_end_of_its_utc_day() -> None:
    assert snapshot_cutoff(date(2026, 10, 15)) == datetime(2026, 10, 16, tzinfo=UTC)
    assert snapshot_cutoff(date(2026, 12, 31)) == datetime(2027, 1, 1, tzinfo=UTC)


def test_the_snapshot_date_is_read_from_the_command_line() -> None:
    assert parse_snapshot_date(["--snapshot-date", "2026-10-15"], "test") == date(2026, 10, 15)


def test_without_a_date_the_snapshot_is_today_in_utc() -> None:
    assert parse_snapshot_date([], "test") == datetime.now(UTC).date()


def test_database_rows_become_a_batch_with_the_exact_agreed_types() -> None:
    dataset = DATASETS_BY_NAME["grow_offers"]
    rows = [
        (
            1, 4, "Okra", 100, "LB", Decimal("3.50"), date(2026, 10, 20), date(2027, 1, 10), 3,
            "OPEN", datetime(2026, 10, 15, 9, 30, tzinfo=UTC),
        ),
        (
            2, 4, "Kale", 40, "BUNCH", Decimal("2.25"), date(2026, 10, 21), date(2026, 12, 1), 5,
            "CANCELLED", datetime(2026, 10, 15, 10, 0, tzinfo=UTC),
        ),
    ]

    batch = to_record_batch(dataset, rows)

    assert batch.schema == dataset.schema
    assert batch.num_rows == 2
    assert batch.column("estimated_price").to_pylist() == [Decimal("3.50"), Decimal("2.25")]
    assert batch.column("created_at").type == pa.timestamp("us", tz="UTC")
