# SPDX-License-Identifier: Apache-2.0
"""Reparse identity and benign meaning checks."""

from __future__ import annotations

import pytest
import sqlglot

from t2sql.guard import check
from t2sql.pipeline import run_sql


def test_reparse_roundtrip() -> None:
    sql = "SELECT id, status FROM orders WHERE id < 5"
    verdict = check(sql)
    assert verdict.ok
    assert verdict.sql is not None
    reparsed = sqlglot.parse_one(verdict.sql, read="postgres")
    assert reparsed.sql(dialect="postgres", comments=False) == verdict.sql


@pytest.mark.parametrize(
    ("variant", "plain"),
    [
        ("SELECT * FROM orders -- trailing", "SELECT * FROM orders"),
        ("SELECT 'a;b' AS s; ", "SELECT 'a;b' AS s"),
        ("SELECT 1 /* nested /* c */ ; DROP */", "SELECT 1"),
        ("select * from ORDERS", "SELECT * FROM orders"),
    ],
)
def test_benign_same_rows(variant: str, plain: str, db_seeded: None) -> None:
    right_sql = check(plain).sql
    left_sql = check(variant).sql
    assert right_sql is not None and left_sql is not None
    left = run_sql(left_sql)
    right = run_sql(right_sql)
    assert left.code == "OK"
    assert right.code == "OK"
    assert left.rows == right.rows
