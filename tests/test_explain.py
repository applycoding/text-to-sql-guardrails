# SPDX-License-Identifier: Apache-2.0
"""EXPLAIN bounds: synthetic plans and live pipeline rows."""

from __future__ import annotations

import pytest

from t2sql import explain
from t2sql.pipeline import run_sql


def test_synthetic_cost_first() -> None:
    plan = [{"Plan": {"Node Type": "Seq Scan", "Total Cost": 60_000, "Plan Rows": 10, "Plans": []}}]
    summary = explain.evaluate(plan)
    ok, code = explain.dry_run_verdict(summary)
    assert ok is False
    assert code == "DRYRUN_COST"


def test_synthetic_rows() -> None:
    plan = [
        {
            "Plan": {
                "Node Type": "Seq Scan",
                "Total Cost": 1,
                "Plan Rows": 2_000_000,
                "Plans": [],
            }
        }
    ]
    summary = explain.evaluate(plan)
    ok, code = explain.dry_run_verdict(summary)
    assert ok is False
    assert code == "DRYRUN_ROWS"


def test_nested_plans_max_rows() -> None:
    plan = [
        {
            "Plan": {
                "Node Type": "Aggregate",
                "Total Cost": 10,
                "Plan Rows": 1,
                "Plans": [
                    {"Node Type": "Seq Scan", "Total Cost": 5, "Plan Rows": 2_000_000, "Plans": []},
                ],
            }
        }
    ]
    summary = explain.evaluate(plan)
    assert summary.max_plan_rows == 2_000_000


def test_malformed_plan_raises() -> None:
    with pytest.raises(ValueError):
        explain.evaluate([{}])


PIPELINE_ROWS = [
    (
        "orders_x_items",
        "SELECT o.id FROM orders o, order_items i",
        "DRYRUN_ROWS",
        192_000_000,
    ),
    (
        "orders_x_customers",
        "SELECT o.id FROM orders o, customers c",
        "DRYRUN_ROWS",
        8_000_000,
    ),
    (
        "items_self_join",
        ("SELECT a.order_id FROM order_items a JOIN order_items b ON a.product_id = b.product_id"),
        "DRYRUN_ROWS",
        4_800_002,
    ),
    (
        "orders_x_items_count",
        "SELECT count(*) FROM orders o, order_items i",
        "DRYRUN_COST",
        2_880_651,
    ),
]


@pytest.mark.parametrize(("case_id", "sql", "expected", "min_rows"), PIPELINE_ROWS)
def test_live_bounds(case_id: str, sql: str, expected: str, min_rows: int, db_seeded: None) -> None:
    _ = case_id
    result = run_sql(sql)
    assert result.code == expected
    print(f"pipeline {case_id} code={result.code}")
