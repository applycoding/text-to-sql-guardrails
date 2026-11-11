# SPDX-License-Identifier: Apache-2.0
"""Executor-level codes and details."""

from __future__ import annotations

import time

import pytest

from t2sql import executor, explain
from t2sql.guard import GuardConfig


def _reset() -> None:
    executor.reset_counters()


def test_exec_timeout(db_seeded: None) -> None:
    _reset()
    start = time.monotonic()
    result = executor.run("SELECT pg_sleep(5)")
    elapsed = time.monotonic() - start
    assert result.code == "EXEC_TIMEOUT"
    assert result.detail.startswith("57014 ")
    assert elapsed >= 1.5


def test_db_error_privilege(db_seeded: None) -> None:
    _reset()
    result = executor.run('SELECT email FROM "shop"."customers" LIMIT 1')
    assert result.code == "DB_ERROR"
    assert result.detail.startswith("42501 ")


def test_dryrun_error_malformed_plan(db_seeded: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _reset()

    def _boom(_plan: object) -> explain.ExplainSummary:
        raise ValueError("missing Plan Rows")

    monkeypatch.setattr(explain, "evaluate", _boom)
    result = executor.run("SELECT id FROM orders LIMIT 1", GuardConfig())
    assert result.code == "DRYRUN_ERROR"


def test_result_too_large(db_seeded: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from t2sql import policy

    _reset()
    monkeypatch.setattr(policy, "MAX_RESULT_BYTES", 1)
    sql = "SELECT id, customer_id, status, ordered_at FROM orders LIMIT 5"
    result = executor.run(sql, GuardConfig(dry_run=False))
    assert result.code == "RESULT_TOO_LARGE"


def test_dryrun_error_missing_keys() -> None:
    with pytest.raises(ValueError, match="missing Plan Rows"):
        explain.evaluate([{"Plan": {"Total Cost": 1.0}}])
