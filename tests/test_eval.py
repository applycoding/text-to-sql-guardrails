# SPDX-License-Identifier: Apache-2.0
"""Stub regression eval against frozen rows."""

from __future__ import annotations

import json
from pathlib import Path

import pg8000.native

from t2sql.model import StubModel
from t2sql.pipeline import run_question

FIXTURE = Path(__file__).parent / "fixtures" / "eval_expected.json"


def _admin_rows(sql: str, admin_conn: pg8000.native.Connection) -> list[list[object]]:
    if not sql:
        return []
    admin_conn.run("SET search_path TO shop, public")
    return [list(row) for row in admin_conn.run(sql)]


def test_eval_regression(db_seeded: None, admin_conn: pg8000.native.Connection) -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    model = StubModel()
    for entry in data["executable"]:
        result = run_question(model, entry["question"])
        assert result.code == "OK", entry["question"]
        assert result.rows is not None
        frozen = entry["rows"]
        if entry.get("min_rows"):
            assert len(result.rows) == entry["min_rows"]
            for i, row in enumerate(frozen):
                assert result.rows[i] == row
        else:
            assert result.rows == frozen
        gold = entry.get("gold_sql")
        if gold:
            gold_rows = _admin_rows(gold, admin_conn)
            assert result.rows == gold_rows
        elif result.sql:
            gold_rows = _admin_rows(result.sql, admin_conn)
            assert result.rows == gold_rows
    for question in data["refusals"]:
        result = run_question(model, question)
        assert result.code == "NO_TEMPLATE", question
