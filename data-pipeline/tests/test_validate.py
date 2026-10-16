from datetime import UTC, datetime

import pyarrow as pa

from ingestion.datasets import DATASETS_BY_NAME
from ingestion.storage import RawStorage
from ingestion.validate import validate_snapshot
from tests.snapshot_builders import SNAPSHOT_DATE, sample_table, write_table, write_valid_snapshot


def test_a_complete_snapshot_is_valid(storage: RawStorage) -> None:
    write_valid_snapshot(storage)

    assert validate_snapshot(storage, SNAPSHOT_DATE) == []


def test_a_snapshot_without_a_manifest_is_refused(storage: RawStorage) -> None:
    [problem] = validate_snapshot(storage, SNAPSHOT_DATE)

    assert "No manifest for snapshot 2026-10-15" in problem


def test_a_dataset_missing_from_the_manifest_is_reported(storage: RawStorage) -> None:
    manifest = write_valid_snapshot(storage)
    del manifest["datasets"]["grow_offers"]
    storage.write_manifest(SNAPSHOT_DATE, manifest)

    assert validate_snapshot(storage, SNAPSHOT_DATE) == ["grow_offers: missing from the manifest"]


def test_an_unknown_dataset_in_the_manifest_is_reported(storage: RawStorage) -> None:
    manifest = write_valid_snapshot(storage)
    manifest["datasets"]["users"] = {"path": "users/x.parquet", "row_count": 1}
    storage.write_manifest(SNAPSHOT_DATE, manifest)

    assert validate_snapshot(storage, SNAPSHOT_DATE) == ["users: in the manifest but not a known dataset"]


def test_a_row_count_that_differs_from_the_extract_is_reported(storage: RawStorage) -> None:
    write_valid_snapshot(storage)
    write_table(storage, "farms", sample_table(DATASETS_BY_NAME["farms"], row_count=1))

    assert validate_snapshot(storage, SNAPSHOT_DATE) == ["farms: holds 1 rows, the extract wrote 2"]


def test_a_changed_column_type_is_reported(storage: RawStorage) -> None:
    write_valid_snapshot(storage)
    products = sample_table(DATASETS_BY_NAME["products"])
    price_index = products.schema.get_field_index("price")
    as_float = products.set_column(
        price_index, pa.field("price", pa.float64()), pa.array([4.5, 4.5], pa.float64())
    )
    write_table(storage, "products", as_float)

    assert validate_snapshot(storage, SNAPSHOT_DATE) == [
        "products: price is double, expected decimal128(10, 2)"
    ]


def test_a_missing_column_is_reported(storage: RawStorage) -> None:
    write_valid_snapshot(storage)
    write_table(storage, "farms", sample_table(DATASETS_BY_NAME["farms"]).drop_columns(["city"]))

    assert validate_snapshot(storage, SNAPSHOT_DATE) == ["farms: missing column city"]


def test_a_repeated_primary_key_is_reported(storage: RawStorage) -> None:
    write_valid_snapshot(storage)
    farms = sample_table(DATASETS_BY_NAME["farms"])
    repeated = farms.set_column(0, "id", pa.array([7, 7], pa.int64()))
    write_table(storage, "farms", repeated)

    assert validate_snapshot(storage, SNAPSHOT_DATE) == ["farms: 1 repeated values of id"]


def test_a_missing_primary_key_is_reported(storage: RawStorage) -> None:
    write_valid_snapshot(storage)
    farms = sample_table(DATASETS_BY_NAME["farms"])
    write_table(storage, "farms", farms.set_column(0, "id", pa.array([1, None], pa.int64())))

    assert validate_snapshot(storage, SNAPSHOT_DATE) == ["farms: 1 rows have no id"]


def test_rows_from_after_the_cutoff_are_reported(storage: RawStorage) -> None:
    write_valid_snapshot(storage)
    history = sample_table(DATASETS_BY_NAME["inventory_history"])
    late = datetime(2026, 10, 16, 0, 0, tzinfo=UTC)
    changed_at = history.schema.get_field_index("changed_at")
    write_table(
        storage,
        "inventory_history",
        history.set_column(
            changed_at, history.schema.field(changed_at), pa.array([late, late], history.schema.field(changed_at).type)
        ),
    )

    assert validate_snapshot(storage, SNAPSHOT_DATE) == [
        "inventory_history: has rows from 2026-10-16T00:00:00+00:00, after the cutoff 2026-10-16T00:00:00+00:00"
    ]


def test_an_unreadable_file_is_reported(storage: RawStorage) -> None:
    write_valid_snapshot(storage)
    with storage.filesystem.open_output_stream(storage.dataset_path("crop_requests", SNAPSHOT_DATE)) as sink:
        sink.write(b"not a parquet file")

    [problem] = validate_snapshot(storage, SNAPSHOT_DATE)

    assert problem.startswith("crop_requests: cannot be read")


def test_an_empty_dataset_is_valid(storage: RawStorage) -> None:
    manifest = write_valid_snapshot(storage)
    empty = sample_table(DATASETS_BY_NAME["crop_commitments"], row_count=0)
    write_table(storage, "crop_commitments", empty)
    manifest["datasets"]["crop_commitments"]["row_count"] = 0
    storage.write_manifest(SNAPSHOT_DATE, manifest)

    assert validate_snapshot(storage, SNAPSHOT_DATE) == []


def test_every_problem_is_reported_not_just_the_first(storage: RawStorage) -> None:
    write_valid_snapshot(storage)
    write_table(storage, "farms", sample_table(DATASETS_BY_NAME["farms"], row_count=3))
    products = sample_table(DATASETS_BY_NAME["products"])
    write_table(storage, "products", products.set_column(0, "id", pa.array([5, 5], pa.int64())))

    problems = validate_snapshot(storage, SNAPSHOT_DATE)

    assert problems == ["farms: holds 3 rows, the extract wrote 2", "products: 1 repeated values of id"]

