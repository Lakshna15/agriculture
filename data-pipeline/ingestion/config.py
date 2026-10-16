"""Where the pipeline reads from and writes to, taken from the environment."""

import os
from dataclasses import dataclass, field

import psycopg


class MissingSettingError(Exception):
    pass


def required_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingSettingError(f"Set {name} in the environment.")
    return value


@dataclass(frozen=True)
class SourceDatabase:
    """The application's PostgreSQL database, which the pipeline only reads."""

    host: str
    port: int
    name: str
    user: str
    password: str = field(repr=False)

    @classmethod
    def from_environment(cls) -> "SourceDatabase":
        # The same variables the backend uses, so one .env configures both.
        return cls(
            host=required_setting("POSTGRES_HOST"),
            port=int(required_setting("POSTGRES_PORT")),
            name=required_setting("POSTGRES_DB"),
            user=required_setting("POSTGRES_USER"),
            password=required_setting("POSTGRES_PASSWORD"),
        )

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=self.name,
            user=self.user,
            password=self.password,
            application_name="farm2local-pipeline",
        )


def raw_data_uri() -> str:
    """Where raw snapshots are stored: a local directory, or later an s3:// URI."""
    return required_setting("RAW_DATA_URI")
