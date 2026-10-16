from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Every placeholder in .env.example starts with this.
PLACEHOLDER_SECRET_PREFIX = "change_me"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and the root .env file."""

    # Errors name the setting but never print its value, so a rejected
    # signing key or password does not end up in startup logs.
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )

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

    @field_validator("jwt_secret_key")
    @classmethod
    def secret_is_not_the_example_placeholder(cls, secret: SecretStr) -> SecretStr:
        # The value in .env.example is public. Anyone who knows it could sign
        # tokens for any account, so the backend refuses to start with it.
        if secret.get_secret_value().lower().startswith(PLACEHOLDER_SECRET_PREFIX):
            raise ValueError("replace the example JWT_SECRET_KEY with a random value of your own")
        return secret

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
