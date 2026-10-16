"""Raw snapshot storage, addressed by URI so a local directory can later become S3.

Layout under the root, one partition per dataset and snapshot date:

    <dataset>/snapshot_date=YYYY-MM-DD/<dataset>.parquet
    _manifests/snapshot_date=YYYY-MM-DD/manifest.json

All access goes through a pyarrow FileSystem, so RAW_DATA_URI=/some/directory
and RAW_DATA_URI=s3://bucket/prefix need the same code; only credentials differ.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import fs

MANIFEST_DIRECTORY = "_manifests"


class ManifestNotFoundError(Exception):
    pass


def _partition(snapshot_date: date) -> str:
    return f"snapshot_date={snapshot_date.isoformat()}"


@dataclass(frozen=True)
class RawStorage:
    filesystem: fs.FileSystem
    root: str

    @classmethod
    def from_uri(cls, uri: str) -> "RawStorage":
        filesystem, root = fs.FileSystem.from_uri(uri)
        return cls(filesystem, root.rstrip("/"))

    def relative_dataset_path(self, dataset_name: str, snapshot_date: date) -> str:
        return str(PurePosixPath(dataset_name, _partition(snapshot_date), f"{dataset_name}.parquet"))

    def dataset_path(self, dataset_name: str, snapshot_date: date) -> str:
        return f"{self.root}/{self.relative_dataset_path(dataset_name, snapshot_date)}"

    def manifest_path(self, snapshot_date: date) -> str:
        return f"{self.root}/{MANIFEST_DIRECTORY}/{_partition(snapshot_date)}/manifest.json"

    @contextmanager
    def parquet_writer(self, path: str, schema: pa.Schema) -> Iterator[pq.ParquetWriter]:
        """Write a Parquet file that appears at `path` only once it is complete.

        Data goes to a temporary file that replaces the target in one rename,
        so a run that fails half way never leaves a truncated file where a
        good one was, and re-running a snapshot overwrites it cleanly.
        """
        self._create_parent(path)
        temporary_path = f"{path}.incomplete"
        try:
            with self.filesystem.open_output_stream(temporary_path) as sink:
                with pq.ParquetWriter(sink, schema) as writer:
                    yield writer
        except BaseException:
            self.filesystem.delete_file(temporary_path)
            raise
        self.filesystem.move(temporary_path, path)

    def read_table(self, path: str) -> pa.Table:
        return pq.read_table(path, filesystem=self.filesystem)

    def write_manifest(self, snapshot_date: date, manifest: dict[str, Any]) -> None:
        path = self.manifest_path(snapshot_date)
        self._create_parent(path)
        with self.filesystem.open_output_stream(path) as sink:
            sink.write(json.dumps(manifest, indent=2, sort_keys=True).encode())

    def read_manifest(self, snapshot_date: date) -> dict[str, Any]:
        path = self.manifest_path(snapshot_date)
        if self.filesystem.get_file_info(path).type is not fs.FileType.File:
            raise ManifestNotFoundError(f"No manifest for snapshot {snapshot_date.isoformat()} at {path}")
        with self.filesystem.open_input_stream(path) as source:
            return json.loads(source.read())

    def delete_manifest(self, snapshot_date: date) -> None:
        path = self.manifest_path(snapshot_date)
        if self.filesystem.get_file_info(path).type is fs.FileType.File:
            self.filesystem.delete_file(path)

    def _create_parent(self, path: str) -> None:
        self.filesystem.create_dir(str(PurePosixPath(path).parent), recursive=True)
