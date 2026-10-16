"""Copy one consistent snapshot of the application database into raw Parquet files.

    python -m ingestion.extract --snapshot-date 2026-10-15
"""

import logging
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

import psycopg
import pyarrow as pa

from ingestion.config import SourceDatabase, raw_data_uri
from ingestion.datasets import DATASETS, Dataset
from ingestion.snapshots import parse_snapshot_date, snapshot_cutoff
from ingestion.storage import RawStorage

logger = logging.getLogger(__name__)

# Rows are streamed from PostgreSQL and written in batches of this size, so a
# large table never has to fit in memory at once.
BATCH_SIZE = 10_000


def open_snapshot_connection(source: SourceDatabase) -> psycopg.Connection:
    """A connection whose transaction sees one unchanging database and cannot write.

    REPEATABLE READ makes every query in the transaction see the database as
    it was at the first one, so the datasets agree with each other even while
    the application keeps running: a reservation is never extracted without
    the product it reserves. READ ONLY means the pipeline cannot change
    application data, whatever privileges its database user has.
    """
    connection = source.connect()
    connection.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    connection.read_only = True
    return connection


def to_record_batch(dataset: Dataset, rows: list[tuple[Any, ...]]) -> pa.RecordBatch:
    columns = list(zip(*rows, strict=True))
    arrays = [
        pa.array(values, type=field.type) for values, field in zip(columns, dataset.schema, strict=True)
    ]
    return pa.RecordBatch.from_arrays(arrays, schema=dataset.schema)


def extract_dataset(
    connection: psycopg.Connection,
    dataset: Dataset,
    storage: RawStorage,
    snapshot_date: date,
    cutoff: datetime,
) -> int:
    """Write one dataset's partition for the snapshot and return how many rows it holds."""
    row_count = 0
    with storage.parquet_writer(storage.dataset_path(dataset.name, snapshot_date), dataset.schema) as writer:
        # A named cursor runs on the server and hands rows over in batches.
        with connection.cursor(name=f"extract_{dataset.name}") as cursor:
            cursor.execute(dataset.query, {"cutoff": cutoff})
            while rows := cursor.fetchmany(BATCH_SIZE):
                writer.write_batch(to_record_batch(dataset, rows))
                row_count += len(rows)
    return row_count


def extract_snapshot(source: SourceDatabase, storage: RawStorage, snapshot_date: date) -> dict[str, Any]:
    """Extract every dataset for a snapshot date, then write its manifest.

    The manifest is removed first and written last. A run that fails part
    way therefore leaves no manifest, and validation refuses the snapshot
    until a run has completed.
    """
    cutoff = snapshot_cutoff(snapshot_date)
    storage.delete_manifest(snapshot_date)

    datasets: dict[str, dict[str, Any]] = {}
    with open_snapshot_connection(source) as connection:
        for dataset in DATASETS:
            row_count = extract_dataset(connection, dataset, storage, snapshot_date, cutoff)
            datasets[dataset.name] = {
                "path": storage.relative_dataset_path(dataset.name, snapshot_date),
                "row_count": row_count,
            }
            logger.info("%-22s %8d rows", dataset.name, row_count)

    manifest = {
        "snapshot_date": snapshot_date.isoformat(),
        "cutoff": cutoff.isoformat(),
        "extracted_at": datetime.now(UTC).isoformat(),
        "source_database": source.name,
        "datasets": datasets,
    }
    storage.write_manifest(snapshot_date, manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    snapshot_date = parse_snapshot_date(argv, "Extract a snapshot of the application database.")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    manifest = extract_snapshot(
        SourceDatabase.from_environment(), RawStorage.from_uri(raw_data_uri()), snapshot_date
    )
    total_rows = sum(entry["row_count"] for entry in manifest["datasets"].values())
    logger.info(
        "Extracted snapshot %s: %d datasets, %d rows, cutoff %s",
        snapshot_date.isoformat(),
        len(manifest["datasets"]),
        total_rows,
        manifest["cutoff"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
