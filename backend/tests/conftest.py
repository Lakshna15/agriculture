from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.main import app

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    """Build a throwaway database from the real migrations, once per test run.

    Tests never touch the development database: the name is always derived by
    appending a suffix, so it cannot equal the configured one.
    """
    settings = get_settings()
    test_database_name = f"{settings.postgres_db}_test"
    test_database_url = settings.database_url.set(database=test_database_name)

    maintenance_engine = create_engine(
        settings.database_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with maintenance_engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{test_database_name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{test_database_name}"'))
    maintenance_engine.dispose()

    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.attributes["database_url"] = test_database_url
    command.upgrade(alembic_config, "head")

    engine = create_engine(test_database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after each test.

    The session joins an outer transaction through savepoints, so application
    code can call commit() and rollback() normally while nothing outlives the test.
    """
    with test_engine.connect() as connection:
        outer_transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            session.close()
            outer_transaction.rollback()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
