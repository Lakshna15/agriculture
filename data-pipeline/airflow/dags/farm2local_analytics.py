"""Daily analytics for Farm2Local: extract, validate, then build the marts.

Each run works on one snapshot date, the run's logical date. Every step
overwrites that date's output instead of adding to it, so a run can be
retried or repeated and leaves the same result:

1. extract: copy the rows created before the end of the date out of the
   application database, in one read-only transaction, into Parquet files.
2. validate: check those files against the extract's manifest. Nothing is
   transformed from an incomplete or malformed snapshot.
3. prepare_transformations: rebuild the dbt staging models and marts from the
   snapshot in DuckDB and run their data quality tests.
"""

from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG
from airflow.timetables.interval import CronDataIntervalTimetable

PIPELINE_DIRECTORY = str(Path(__file__).resolve().parents[2])

with DAG(
    dag_id="farm2local_analytics",
    description="Extract, validate and transform a daily snapshot of the marketplace.",
    # Daily data intervals, not Airflow 3's default of plain cron triggers.
    # The run that starts at midnight then has the day just ended as its
    # logical date, so its snapshot is of a complete day whose cutoff has
    # already passed, and repeating the run selects exactly the same rows.
    schedule=CronDataIntervalTimetable("@daily", timezone="UTC"),
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    # Each run rebuilds the marts from its own complete snapshot, so missed
    # days need no catching up: the next run already includes their data.
    catchup=False,
    # Runs share the raw files and the DuckDB warehouse, so they never overlap.
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["farm2local", "analytics"],
) as dag:
    # {{ ds }} is the run's logical date, which Airflow fills in when the task runs.
    extract = BashOperator(
        task_id="extract",
        bash_command="python -m ingestion.extract --snapshot-date {{ ds }}",
        cwd=PIPELINE_DIRECTORY,
    )

    validate = BashOperator(
        task_id="validate",
        bash_command="python -m ingestion.validate --snapshot-date {{ ds }}",
        cwd=PIPELINE_DIRECTORY,
    )

    prepare_transformations = BashOperator(
        task_id="prepare_transformations",
        bash_command=(
            "dbt build --project-dir dbt --profiles-dir dbt"
            " --vars '{\"snapshot_date\": \"{{ ds }}\"}'"
        ),
        cwd=PIPELINE_DIRECTORY,
    )

    extract >> validate >> prepare_transformations
