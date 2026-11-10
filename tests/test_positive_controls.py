# SPDX-License-Identifier: Apache-2.0
"""PLAN section 10 positive controls."""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from t2sql.guard import GuardConfig, check
from t2sql.pipeline import run_sql


def test_single_statement_on_off() -> None:
    sql = "SELECT 1; SELECT 2"
    assert check(sql, GuardConfig()).code == "MULTI_STATEMENT"
    off = check(sql, GuardConfig(single_statement=False))
    assert off.ok
    assert off.sql is not None


def test_statement_type_on_off() -> None:
    sql = "SELECT * FROM orders FOR UPDATE"
    assert check(sql, GuardConfig()).code == "LOCKING_CLAUSE"
    assert check(sql, GuardConfig(statement_type=False)).code != "LOCKING_CLAUSE"


def test_tables_on_off() -> None:
    sql = "SELECT * FROM staff_salaries"
    assert check(sql, GuardConfig()).code == "TABLE_NOT_ALLOWED"
    assert check(sql, GuardConfig(tables=False)).code != "TABLE_NOT_ALLOWED"


def test_nodes_on_off(db_seeded: None) -> None:
    sql = "SELECT pg_sleep(5)"
    assert check(sql, GuardConfig()).code == "FUNCTION_NOT_ALLOWED"
    assert check(sql, GuardConfig(nodes=False)).code == "OK"


def test_columns_on_off(db_seeded: None) -> None:
    sql = "SELECT email FROM customers"
    assert check(sql, GuardConfig()).code == "COLUMN_NOT_ALLOWED"
    assert check(sql, GuardConfig(columns=False)).code == "OK"


def test_limit_on_off() -> None:
    sql = "SELECT id FROM orders"
    on = check(sql, GuardConfig())
    assert on.ok and on.sql and "LIMIT 100" in on.sql
    off = check(sql, GuardConfig(limit=False))
    tree = sqlglot.parse_one(off.sql or "", read="postgres")
    assert not any(isinstance(n, exp.Limit) for n in tree.walk())


def test_dry_run_on_off(db_seeded: None) -> None:
    sql = "SELECT o.id FROM orders o, order_items i"
    assert run_sql(sql, GuardConfig()).code == "DRYRUN_ROWS"
    off = run_sql(sql, GuardConfig(dry_run=False))
    assert off.code == "OK"
    assert off.rows is not None
    assert len(off.rows) == 100
