from pathlib import Path

import pytest

from ingestion.storage import RawStorage


@pytest.fixture
def storage(tmp_path: Path) -> RawStorage:
    return RawStorage.from_uri(str(tmp_path / "raw"))
