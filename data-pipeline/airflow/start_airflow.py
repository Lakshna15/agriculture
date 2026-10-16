"""Run an Airflow command with Airflow's own records kept in PostgreSQL.

    python airflow/start_airflow.py standalone
    python airflow/start_airflow.py dags test farm2local_analytics 2026-10-15

Airflow tracks its runs and task states in a database of its own,
<POSTGRES_DB>_airflow, on the project's PostgreSQL server. It is created on
first use and kept apart from the application's database, which Airflow
never writes to. The connection is built here from the same settings the
backend uses, so no credentials are written into any configuration file.
"""

import os
import subprocess
import sys
from urllib.parse import quote

import psycopg
from psycopg import sql


def required_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"Set {name} in the environment.")
    return value


def ensure_database_exists(connection_settings: dict[str, str], database_name: str) -> None:
    with psycopg.connect(dbname="postgres", autocommit=True, **connection_settings) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
        ).fetchone()
        if exists is None:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))


def main(airflow_arguments: list[str]) -> None:
    connection_settings = {
        "host": required_setting("POSTGRES_HOST"),
        "port": required_setting("POSTGRES_PORT"),
        "user": required_setting("POSTGRES_USER"),
        "password": required_setting("POSTGRES_PASSWORD"),
    }
    metadata_database = f"{required_setting('POSTGRES_DB')}_airflow"
    ensure_database_exists(connection_settings, metadata_database)

    os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"] = (
        "postgresql+psycopg2://"
        f"{quote(connection_settings['user'], safe='')}:{quote(connection_settings['password'], safe='')}"
        f"@{connection_settings['host']}:{connection_settings['port']}/{quote(metadata_database, safe='')}"
    )
    # Brings Airflow's schema up to date. It does nothing when it already is.
    subprocess.run(["airflow", "db", "migrate"], check=True)
    os.execvp("airflow", ["airflow", *airflow_arguments])


if __name__ == "__main__":
    main(sys.argv[1:] or ["standalone"])
