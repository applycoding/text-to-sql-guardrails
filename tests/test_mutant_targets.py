# SPDX-License-Identifier: Apache-2.0
"""Targeted tests for mutation check M1 to M12."""

from __future__ import annotations

from t2sql.guard import check
from t2sql.pipeline import run_sql


def test_m1_stacked() -> None:
    assert check("SELECT 1; DROP TABLE shop.orders").code == "MULTI_STATEMENT"


def test_m2_do_block() -> None:
    assert check("DO $$ BEGIN PERFORM pg_sleep(1); END $$").code == "STATEMENT_NOT_ALLOWED"


def test_m3_cte_shadow() -> None:
    sql = "WITH customers AS (SELECT 1 AS id) SELECT * FROM customers"
    assert check(sql).code == "CTE_SHADOWS_TABLE"


def test_m4_public_orders() -> None:
    assert check("SELECT * FROM public.orders").code == "TABLE_NOT_ALLOWED"


def test_m5_dblink_from() -> None:
    sql = "SELECT * FROM dblink('host=evil', 'select 1') AS t(a int)"
    assert check(sql).code == "FUNCTION_NOT_ALLOWED"


def test_m6_email() -> None:
    assert check("SELECT email FROM customers").code == "COLUMN_NOT_ALLOWED"


def test_m7_limit_clamp(db_seeded: None) -> None:
    result = run_sql("SELECT id FROM orders LIMIT 5000")
    assert result.code == "OK"
    assert result.rows is not None
    assert len(result.rows) == 100


def test_m8_whole_row() -> None:
    assert check("SELECT c FROM customers c").code == "WHOLE_ROW_REFERENCE"


def test_m9_dryrun_rows(db_seeded: None) -> None:
    result = run_sql("SELECT o.id FROM orders o, order_items i")
    assert result.code == "DRYRUN_ROWS"


def test_m10_synthetic_cost() -> None:
    from t2sql import explain

    plan = [{"Plan": {"Total Cost": 60000, "Plan Rows": 10}}]
    summary = explain.evaluate(plan)
    _ok, code = explain.dry_run_verdict(summary)
    assert code == "DRYRUN_COST"


def test_m11_regclass_cast() -> None:
    assert check("SELECT 'pg_authid'::regclass").code == "CAST_NOT_ALLOWED"


def test_m12_pow() -> None:
    assert check("SELECT 2 ^ 1000000000").code == "FUNCTION_NOT_ALLOWED"
