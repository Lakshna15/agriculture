"""Recreate the empty database that the browser tests run against.

The backend-e2e container runs this before applying migrations, so every test
run starts from an empty schema. Only a database whose name ends in "_e2e" is
ever dropped, so a misconfigured environment cannot wipe development data.
"""

import re
import sys

from sqlalchemy import create_engine, text

from app.config import get_settings

E2E_DATABASE_NAME_PATTERN = re.compile(r"^[a-z0-9_]+_e2e$")


def main() -> int:
    settings = get_settings()
    database_name = settings.postgres_db
    if not E2E_DATABASE_NAME_PATTERN.fullmatch(database_name):
        print(
            f"Refusing to reset {database_name!r}: only a database named like 'name_e2e' may be reset.",
            file=sys.stderr,
        )
        return 1

    maintenance_engine = create_engine(
        settings.database_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with maintenance_engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    maintenance_engine.dispose()
    print(f"Recreated empty database {database_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
