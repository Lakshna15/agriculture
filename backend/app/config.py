from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables and the root .env file."""

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # HS256 needs a key of at least 256 bits to be worth its digest size.
    jwt_secret_key: SecretStr = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=60, gt=0)

    # Calendar dates such as a pickup day or an event day belong to the place
    # the marketplace serves, not to the server's clock, which runs in UTC.
    marketplace_timezone: str = "America/New_York"

    @field_validator("marketplace_timezone")
    @classmethod
    def timezone_must_exist(cls, timezone_name: str) -> str:
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"unknown time zone: {timezone_name}") from error
        return timezone_name

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
            # The postgis/postgis image appends its tiger geocoder and topology
            # schemas to the database search path. Pinning it to public keeps
            # unqualified names, and Alembic's schema reflection, limited to
            # application tables.
            query={"options": "-csearch_path=public"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
