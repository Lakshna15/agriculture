"""Check a raw snapshot before any transformation reads it.

    python -m ingestion.validate --snapshot-date 2026-10-15

This checks the files themselves: every dataset the pipeline expects is
present and complete, has exactly the agreed columns and types, holds as many
rows as the extract wrote, has a unique non-null primary key and contains
nothing created after the snapshot's cutoff. Rules about the data's meaning,
such as allowed statuses and links between tables, are dbt tests.
"""

import logging
import sys
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from ingestion.config import raw_data_uri
from ingestion.datasets import DATASETS, DATASETS_BY_NAME, Dataset
from ingestion.snapshots import parse_snapshot_date, snapshot_cutoff
from ingestion.storage import ManifestNotFoundError, RawStorage

logger = logging.getLogger(__name__)


def _describe_schema_difference(expected: pa.Schema, actual: pa.Schema) -> str:
    expected_columns = {field.name: field.type for field in expected}
    actual_columns = {field.name: field.type for field in actual}
    differences = []
    for name in expected.names:
        if name not in actual_columns:
            differences.append(f"missing column {name}")
        elif actual_columns[name] != expected_columns[name]:
            differences.append(f"{name} is {actual_columns[name]}, expected {expected_columns[name]}")
    differences.extend(f"unexpected column {name}" for name in actual.names if name not in expected_columns)
    if not differences and expected.names != actual.names:
        differences.append("columns are in a different order")
    return "; ".join(differences)


def check_dataset(table: pa.Table, dataset: Dataset, expected_rows: int, cutoff: datetime) -> list[str]:
    """Problems with one dataset's file, or an empty list if it is sound."""
    if not table.schema.equals(dataset.schema):
        return [f"{dataset.name}: {_describe_schema_difference(dataset.schema, table.schema)}"]

    problems = []
    if table.num_rows != expected_rows:
        problems.append(f"{dataset.name}: holds {table.num_rows} rows, the extract wrote {expected_rows}")

    key = table.column(dataset.primary_key)
    if key.null_count:
        problems.append(f"{dataset.name}: {key.null_count} rows have no {dataset.primary_key}")
    duplicates = len(key) - key.null_count - pc.count_distinct(key).as_py()
    if duplicates:
        problems.append(f"{dataset.name}: {duplicates} repeated values of {dataset.primary_key}")

    created = table.column(dataset.created_column)
    if created.null_count:
        problems.append(f"{dataset.name}: {created.null_count} rows have no {dataset.created_column}")
    latest = pc.max(created).as_py()
    if latest is not None and latest >= cutoff:
        problems.append(
            f"{dataset.name}: has rows from {latest.isoformat()}, after the cutoff {cutoff.isoformat()}"
        )
    return problems


def validate_snapshot(storage: RawStorage, snapshot_date: date) -> list[str]:
    """Every problem found in a snapshot. An empty list means it may be transformed."""
    try:
        manifest: dict[str, Any] = storage.read_manifest(snapshot_date)
    except ManifestNotFoundError as error:
        return [f"{error}. Run the extract for this date first."]

    problems = []
    if manifest.get("snapshot_date") != snapshot_date.isoformat():
        problems.append(f"The manifest is for {manifest.get('snapshot_date')}, not {snapshot_date.isoformat()}")

    cutoff = snapshot_cutoff(snapshot_date)
    entries: dict[str, Any] = manifest.get("datasets", {})
    for dataset in DATASETS:
        entry = entries.get(dataset.name)
        if entry is None:
            problems.append(f"{dataset.name}: missing from the manifest")
            continue
        try:
            table = storage.read_table(storage.dataset_path(dataset.name, snapshot_date))
        except (OSError, pa.ArrowException) as error:
            problems.append(f"{dataset.name}: cannot be read ({error})")
            continue
        problems.extend(check_dataset(table, dataset, entry["row_count"], cutoff))

    problems.extend(
        f"{name}: in the manifest but not a known dataset"
        for name in sorted(set(entries) - set(DATASETS_BY_NAME))
    )
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    snapshot_date = parse_snapshot_date(argv, "Validate a raw snapshot before transforming it.")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    problems = validate_snapshot(RawStorage.from_uri(raw_data_uri()), snapshot_date)
    if problems:
        for problem in problems:
            logger.error("INVALID %s", problem)
        logger.error("Snapshot %s failed validation with %d problems", snapshot_date.isoformat(), len(problems))
        return 1
    logger.info("Snapshot %s is valid: %d datasets checked", snapshot_date.isoformat(), len(DATASETS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
