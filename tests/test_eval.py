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
    admin_conn.run("SET search_path TO shop, public")
    rows: list[list[object]] = []
    for row in admin_conn.run(sql):
        cells: list[object] = []
        for cell in row:
            if hasattr(cell, "isoformat"):
                cells.append(cell.isoformat())
            else:
                cells.append(cell)
        rows.append(cells)
    return rows


def test_eval_regression(db_seeded: None, admin_conn: pg8000.native.Connection) -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    model = StubModel()
    for entry in data["executable"]:
        result = run_question(model, entry["question"])
        assert result.code == "OK", entry["question"]
        assert result.rows is not None
        assert result.rows == entry["rows"]
        gold = entry["gold_sql"]
        gold_rows = _admin_rows(gold, admin_conn)
        assert result.rows == gold_rows
    for question in data["refusals"]:
        result = run_question(model, question)
        assert result.code == "NO_TEMPLATE", question
