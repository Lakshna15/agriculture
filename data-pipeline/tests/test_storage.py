from datetime import date
from pathlib import Path

import pyarrow as pa
import pytest

from ingestion.storage import ManifestNotFoundError, RawStorage

SNAPSHOT_DATE = date(2026, 10, 15)
SCHEMA = pa.schema([("id", pa.int64()), ("name", pa.string())])


def write_rows(storage: RawStorage, path: str, ids: list[int]) -> None:
    with storage.parquet_writer(path, SCHEMA) as writer:
        writer.write_table(pa.table({"id": ids, "name": [f"row {value}" for value in ids]}, schema=SCHEMA))


def test_partitions_are_laid_out_by_dataset_and_snapshot_date(storage: RawStorage, tmp_path: Path) -> None:
    assert storage.relative_dataset_path("farms", SNAPSHOT_DATE) == (
        "farms/snapshot_date=2026-10-15/farms.parquet"
    )
    assert storage.dataset_path("farms", SNAPSHOT_DATE) == (
        f"{(tmp_path / 'raw').as_posix()}/farms/snapshot_date=2026-10-15/farms.parquet"
    )
    assert storage.manifest_path(SNAPSHOT_DATE).endswith("/_manifests/snapshot_date=2026-10-15/manifest.json")


def test_a_file_uri_and_a_plain_path_address_the_same_files(tmp_path: Path) -> None:
    by_path = RawStorage.from_uri(str(tmp_path / "raw"))
    by_uri = RawStorage.from_uri((tmp_path / "raw").as_uri())
    write_rows(by_path, by_path.dataset_path("farms", SNAPSHOT_DATE), [1])

    assert by_uri.read_table(by_uri.dataset_path("farms", SNAPSHOT_DATE)).column("id").to_pylist() == [1]


def test_writing_a_partition_again_replaces_it(storage: RawStorage) -> None:
    path = storage.dataset_path("farms", SNAPSHOT_DATE)
    write_rows(storage, path, [1, 2, 3])

    write_rows(storage, path, [4])

    assert storage.read_table(path).column("id").to_pylist() == [4]


def test_a_failed_write_keeps_the_previous_file_and_leaves_nothing_half_written(
    storage: RawStorage, tmp_path: Path
) -> None:
    path = storage.dataset_path("farms", SNAPSHOT_DATE)
    write_rows(storage, path, [1, 2])

    with pytest.raises(RuntimeError, match="connection lost"):
        with storage.parquet_writer(path, SCHEMA) as writer:
            writer.write_table(pa.table({"id": [9], "name": ["partial"]}, schema=SCHEMA))
            raise RuntimeError("connection lost")

    assert storage.read_table(path).column("id").to_pylist() == [1, 2]
    partition = tmp_path / "raw" / "farms" / "snapshot_date=2026-10-15"
    assert [file.name for file in partition.iterdir()] == ["farms.parquet"]


def test_manifests_round_trip_and_can_be_removed(storage: RawStorage) -> None:
    storage.write_manifest(SNAPSHOT_DATE, {"snapshot_date": "2026-10-15", "datasets": {}})

    assert storage.read_manifest(SNAPSHOT_DATE)["snapshot_date"] == "2026-10-15"

    storage.delete_manifest(SNAPSHOT_DATE)
    with pytest.raises(ManifestNotFoundError):
        storage.read_manifest(SNAPSHOT_DATE)


def test_removing_a_manifest_that_does_not_exist_is_harmless(storage: RawStorage) -> None:
    storage.delete_manifest(SNAPSHOT_DATE)
