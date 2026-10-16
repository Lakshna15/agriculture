"""The DAG as Airflow itself loads it.

Airflow is installed in its own environment, apart from the pipeline's, so
the DAG is loaded by Airflow's interpreter in a subprocess that reports what
it found.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

PIPELINE_DIRECTORY = Path(__file__).resolve().parents[1]
DAGS_FOLDER = PIPELINE_DIRECTORY / "airflow" / "dags"

LOAD_DAGS = """
import json, sys
import pendulum
from airflow.dag_processing.dagbag import DagBag
from airflow.timetables.base import DataInterval, TimeRestriction

bag = DagBag(dag_folder=sys.argv[1])
report = {"import_errors": {str(path): str(error) for path, error in bag.import_errors.items()}, "dags": {}}
for dag_id, dag in bag.dags.items():
    environment = dag.get_template_env()
    # The scheduled run after the one for 14 October.
    next_run = dag.timetable.next_dagrun_info(
        last_automated_data_interval=DataInterval(
            pendulum.datetime(2026, 10, 14, tz="UTC"), pendulum.datetime(2026, 10, 15, tz="UTC")
        ),
        restriction=TimeRestriction(earliest=None, latest=None, catchup=True),
    )
    report["dags"][dag_id] = {
        "next_run": {
            "logical_date": next_run.logical_date.isoformat(),
            "runs_at": next_run.run_after.isoformat(),
        },
        "catchup": dag.catchup,
        "max_active_runs": dag.max_active_runs,
        "tasks": {
            task.task_id: {
                "upstream": sorted(task.upstream_task_ids),
                "command": environment.from_string(task.bash_command).render(ds="2026-10-15"),
                "cwd": task.cwd,
                "retries": task.retries,
            }
            for task in dag.tasks
        },
    }
print(json.dumps(report))
"""


@pytest.fixture(scope="module")
def loaded_dags() -> dict[str, Any]:
    airflow_python = os.environ.get("AIRFLOW_PYTHON")
    if not airflow_python:
        pytest.skip("AIRFLOW_PYTHON is not set; run the tests in the pipeline container")
    result = subprocess.run(
        [airflow_python, "-c", LOAD_DAGS, str(DAGS_FOLDER)],
        capture_output=True,
        text=True,
        # Not the pipeline directory: its airflow/ folder must not be mistaken for the package.
        cwd="/",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_the_dag_folder_loads_without_errors(loaded_dags: dict[str, Any]) -> None:
    assert loaded_dags["import_errors"] == {}
    assert list(loaded_dags["dags"]) == ["farm2local_analytics"]


def test_the_run_at_midnight_works_on_the_day_that_just_ended(loaded_dags: dict[str, Any]) -> None:
    # A snapshot of a finished day, whose cutoff has passed before the run starts.
    assert loaded_dags["dags"]["farm2local_analytics"]["next_run"] == {
        "logical_date": "2026-10-15T00:00:00+00:00",
        "runs_at": "2026-10-16T00:00:00+00:00",
    }


def test_the_pipeline_runs_one_run_at_a_time_without_backfilling(loaded_dags: dict[str, Any]) -> None:
    dag = loaded_dags["dags"]["farm2local_analytics"]

    assert dag["catchup"] is False
    assert dag["max_active_runs"] == 1


def test_extract_then_validate_then_prepare_transformations(loaded_dags: dict[str, Any]) -> None:
    tasks = loaded_dags["dags"]["farm2local_analytics"]["tasks"]

    assert {task_id: task["upstream"] for task_id, task in tasks.items()} == {
        "extract": [],
        "validate": ["extract"],
        "prepare_transformations": ["validate"],
    }


def test_every_step_works_on_the_runs_logical_date(loaded_dags: dict[str, Any]) -> None:
    tasks = loaded_dags["dags"]["farm2local_analytics"]["tasks"]

    assert tasks["extract"]["command"] == "python -m ingestion.extract --snapshot-date 2026-10-15"
    assert tasks["validate"]["command"] == "python -m ingestion.validate --snapshot-date 2026-10-15"
    assert tasks["prepare_transformations"]["command"] == (
        "dbt build --project-dir dbt --profiles-dir dbt --vars '{\"snapshot_date\": \"2026-10-15\"}'"
    )
    assert {task["cwd"] for task in tasks.values()} == {str(PIPELINE_DIRECTORY)}
    assert {task["retries"] for task in tasks.values()} == {1}
