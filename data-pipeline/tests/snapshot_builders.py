"""Small, valid raw snapshots for tests that do not need a database."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pyarrow as pa

from ingestion.datasets import DATASETS, Dataset
from ingestion.storage import RawStorage

SNAPSHOT_DATE = date(2026, 10, 15)
CREATED_AT = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


def _sample_value(field: pa.Field, row_number: int) -> Any:
    data_type = field.type
    if pa.types.is_timestamp(data_type):
        return CREATED_AT
    if pa.types.is_integer(data_type):
        return row_number
    if pa.types.is_string(data_type):
        return f"{field.name}-{row_number}"
    if pa.types.is_boolean(data_type):
        return True
    if pa.types.is_date32(data_type):
        return SNAPSHOT_DATE
    if pa.types.is_decimal(data_type):
        return Decimal("4.50")
    if pa.types.is_floating(data_type):
        return 35.2
    raise TypeError(f"No sample value for {field.name} of type {data_type}")


def sample_table(dataset: Dataset, row_count: int = 2) -> pa.Table:
    rows = [
        {field.name: _sample_value(field, row_number) for field in dataset.schema}
        for row_number in range(1, row_count + 1)
    ]
    return pa.Table.from_pylist(rows, schema=dataset.schema)


def write_table(storage: RawStorage, dataset_name: str, table: pa.Table) -> None:
    with storage.parquet_writer(storage.dataset_path(dataset_name, SNAPSHOT_DATE), table.schema) as writer:
        writer.write_table(table)


def write_valid_snapshot(storage: RawStorage) -> dict[str, Any]:
    """Write every dataset with two rows and a manifest that matches them."""
    datasets = {}
    for dataset in DATASETS:
        table = sample_table(dataset)
        write_table(storage, dataset.name, table)
        datasets[dataset.name] = {
            "path": storage.relative_dataset_path(dataset.name, SNAPSHOT_DATE),
            "row_count": table.num_rows,
        }
    manifest = {"snapshot_date": SNAPSHOT_DATE.isoformat(), "datasets": datasets}
    storage.write_manifest(SNAPSHOT_DATE, manifest)
    return manifest
