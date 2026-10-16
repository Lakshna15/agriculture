FROM apache/airflow:3.3.2-python3.12

# The interpreter Airflow itself is installed for. Checked here so a change in
# the base image fails the build instead of the DAG test.
ENV AIRFLOW_PYTHON=/usr/local/bin/python
RUN ${AIRFLOW_PYTHON} -c "import airflow"

USER root
RUN mkdir -p /opt/pipeline-venv /opt/farm2local/data-pipeline \
    && chown -R airflow:0 /opt/pipeline-venv /opt/farm2local
USER airflow

# The pipeline's libraries and dbt live in their own virtual environment, so
# the versions Airflow pins and the versions the pipeline pins never have to
# agree. Airflow only orchestrates; every task runs in this environment.
COPY --chown=airflow:0 requirements.txt requirements-dev.txt /opt/pipeline-requirements/
RUN ${AIRFLOW_PYTHON} -m venv /opt/pipeline-venv \
    && /opt/pipeline-venv/bin/pip install --no-cache-dir -r /opt/pipeline-requirements/requirements-dev.txt

ENV PATH="/opt/pipeline-venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DO_NOT_TRACK=1 \
    RAW_DATA_URI=/opt/farm2local/data-pipeline/data/raw \
    DUCKDB_PATH=/opt/farm2local/data-pipeline/data/warehouse/farm2local.duckdb \
    AIRFLOW__CORE__DAGS_FOLDER=/opt/farm2local/data-pipeline/airflow/dags \
    AIRFLOW__CORE__LOAD_EXAMPLES=False

WORKDIR /opt/farm2local/data-pipeline
COPY --chown=airflow:0 . .

# The base image's entrypoint treats its first argument as an Airflow command.
# Commands here are run as given; airflow/start_airflow.py prepares Airflow.
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["python", "airflow/start_airflow.py", "standalone"]
