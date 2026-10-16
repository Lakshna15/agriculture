"""What a snapshot date means, shared by the extract and validate commands."""

import argparse
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta


def snapshot_cutoff(snapshot_date: date) -> datetime:
    """The end of the snapshot date in UTC.

    A snapshot holds every row created before this moment. Fixing the cutoff
    to the date, rather than to when the extract happens to run, means a
    snapshot re-run later selects the same rows.
    """
    return datetime.combine(snapshot_date + timedelta(days=1), time.min, tzinfo=UTC)


def parse_snapshot_date(argv: Sequence[str] | None, description: str) -> date:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--snapshot-date",
        type=date.fromisoformat,
        default=None,
        help="The snapshot to work on, as YYYY-MM-DD. Defaults to today in UTC.",
    )
    arguments = parser.parse_args(argv)
    return arguments.snapshot_date or datetime.now(UTC).date()
