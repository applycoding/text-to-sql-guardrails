# SPDX-License-Identifier: Apache-2.0
"""EXPLAIN bounds: synthetic plans and live pipeline rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from t2sql import explain
from t2sql.model import StubModel
from t2sql.pipeline import run_sql

FIXTURE = Path(__file__).parent / "fixtures" / "eval_expected.json"


def test_synthetic_cost_first() -> None:
    plan = [
        {
            "Plan": {
                "Node Type": "Seq Scan",
                "Total Cost": 60_000,
                "Plan Rows": 2_000_000,
                "Plans": [],
            }
        }
    ]
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


def test_nested_plans_initplan() -> None:
    plan = [
        {
            "Plan": {
                "Node Type": "Aggregate",
                "Total Cost": 10,
                "Plan Rows": 1,
                "Plans": [
                    {
                        "Node Type": "Seq Scan",
                        "Total Cost": 5,
                        "Plan Rows": 2_000_000,
                        "Parent Relationship": "InitPlan",
                        "Plans": [],
                    },
                ],
            }
        }
    ]
    summary = explain.evaluate(plan)
    assert summary.max_plan_rows == 2_000_000


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
        (
            "SELECT a.order_id FROM order_items a "
            "JOIN order_items b ON a.product_id = b.product_id"
        ),
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


@pytest.mark.parametrize(("case_id", "sql", "expected", "min_bound"), PIPELINE_ROWS)
def test_live_bounds(
    case_id: str, sql: str, expected: str, min_bound: int, db_seeded: None
) -> None:
    import json
    import os

    import pg8000.native

    from t2sql.guard import check

    result = run_sql(sql)
    assert result.code == expected
    verdict = check(sql)
    assert verdict.sql
    conn = pg8000.native.Connection(
        host=os.environ.get("T2SQL_DSN_HOST", "localhost"),
        user="t2s_reader",
        password=os.environ.get("T2SQL_READER_PASSWORD", "ci_reader"),
        database="postgres",
    )
    conn.run("BEGIN READ ONLY")
    raw = conn.run(f"EXPLAIN (FORMAT JSON) {verdict.sql}")
    plan_row = raw[0][0]
    plan_json = json.loads(plan_row) if isinstance(plan_row, str) else plan_row
    summary = explain.evaluate(plan_json)
    conn.close()
    if expected == "DRYRUN_ROWS":
        assert summary.max_plan_rows >= min_bound
        print(f"pipeline {case_id} max_rows={summary.max_plan_rows} ref={min_bound}")
    else:
        assert summary.total_cost >= min_bound
        print(f"pipeline {case_id} total_cost={summary.total_cost} ref={min_bound}")


def test_eval_questions_within_plan_caps(db_seeded: None) -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    model = StubModel()
    max_cost = 0.0
    max_rows = 0.0
    for entry in data["executable"]:
        from t2sql.guard import check

        sql = model.to_sql(entry["question"])
        assert sql is not None
        verdict = check(sql)
        assert verdict.ok and verdict.sql
        import pg8000.native

        conn = pg8000.native.Connection(
            host="localhost",
            user="t2s_reader",
            password="ci_reader",
            database="postgres",
        )
        conn.run("BEGIN READ ONLY")
        raw = conn.run(f"EXPLAIN (FORMAT JSON) {verdict.sql}")
        plan_row = raw[0][0]
        plan_json = json.loads(plan_row) if isinstance(plan_row, str) else plan_row
        summary = explain.evaluate(plan_json)
        max_cost = max(max_cost, summary.total_cost)
        max_rows = max(max_rows, summary.max_plan_rows)
        conn.close()
    print(f"eval_max_cost={max_cost} eval_max_rows={max_rows}")
    assert max_cost <= 50_000
    assert max_rows <= 1_000_000
