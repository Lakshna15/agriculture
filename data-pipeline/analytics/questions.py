"""The business questions the pipeline answers, as queries on the dbt marts.

    python -m analytics.questions

Reads the DuckDB warehouse at DUCKDB_PATH, read-only, after a dbt build.
"""

import os
import sys
from dataclasses import dataclass
from typing import Any

import duckdb


@dataclass(frozen=True)
class Question:
    title: str
    query: str


@dataclass(frozen=True)
class Answer:
    question: Question
    columns: list[str]
    rows: list[tuple[Any, ...]]


QUESTIONS: tuple[Question, ...] = (
    Question(
        "Which crops are most searched?",
        """
        select crop_name, searches, no_result_searches
        from mart_unfulfilled_crop_demand
        where searches > 0
        order by searches desc, crop_name
        limit 10
        """,
    ),
    Question(
        "Which crops frequently return no results?",
        """
        select crop_name, no_result_searches, searches, no_result_rate
        from mart_unfulfilled_crop_demand
        where no_result_searches > 0
        order by no_result_searches desc, no_result_rate desc, crop_name
        limit 10
        """,
    ),
    Question(
        "Which regions show the highest unmet demand?",
        """
        select region_id, unmet_demand_signals, unmet_requests, no_result_searches, listings_available
        from mart_demand_by_region
        where unmet_demand_signals > 0
        order by unmet_demand_signals desc, region_id
        limit 10
        """,
    ),
    Question(
        "Which farms have the fastest inventory turnover?",
        """
        select farm_name, days_of_inventory, inventory_turnover, sold_value, average_stock_value
        from mart_inventory_turnover
        where days_of_inventory is not null
        order by days_of_inventory, farm_name
        limit 10
        """,
    ),
    Question(
        "What percentage of Grow Offers reach commitment?",
        """
        select
            count(*) as grow_offers,
            count(*) filter (where reached_minimum) as reached_minimum,
            round(100 * count(*) filter (where reached_minimum) / nullif(count(*), 0), 1) as percent_reached
        from mart_crop_commitment_conversion
        """,
    ),
    Question(
        "What crops show strong demand but low supply?",
        """
        select crop_name, demand_per_listing, searches, customers_waiting, listings_available, active_grow_offers
        from mart_unfulfilled_crop_demand
        where unmet_demand_signals > 0
        order by demand_per_listing desc, crop_name
        limit 10
        """,
    ),
)


def answer_questions(connection: duckdb.DuckDBPyConnection) -> list[Answer]:
    answers = []
    for question in QUESTIONS:
        result = connection.execute(question.query)
        columns = [description[0] for description in result.description]
        answers.append(Answer(question, columns, result.fetchall()))
    return answers


def format_answer(answer: Answer) -> str:
    lines = [answer.question.title]
    if not answer.rows:
        lines.append("  (no data yet)")
        return "\n".join(lines)
    cells = [answer.columns] + [["" if value is None else str(value) for value in row] for row in answer.rows]
    widths = [max(len(row[index]) for row in cells) for index in range(len(answer.columns))]
    for row in cells:
        lines.append("  " + "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)))
    return "\n".join(lines)


def main() -> int:
    with duckdb.connect(os.environ["DUCKDB_PATH"], read_only=True) as connection:
        print("\n\n".join(format_answer(answer) for answer in answer_questions(connection)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
