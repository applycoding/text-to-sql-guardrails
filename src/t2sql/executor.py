# SPDX-License-Identifier: Apache-2.0
"""PostgreSQL executor: dry run and read-only execution."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import pg8000.native

from t2sql import explain, policy
from t2sql.guard import GuardConfig

TIMEOUT_SQL = f"SET LOCAL statement_timeout = '{policy.STATEMENT_TIMEOUT_MS // 1000}s'"


@dataclass(frozen=True)
class ExecResult:
    ok: bool
    code: str
    detail: str
    sql: str | None
    rows: list[list[Any]] | None


def _dsn() -> dict[str, Any]:
    return {
        "host": os.environ.get("T2SQL_DSN_HOST", "postgres"),
        "port": int(os.environ.get("T2SQL_DSN_PORT", "5432")),
        "database": os.environ.get("T2SQL_DSN_DATABASE", "postgres"),
        "user": os.environ.get("T2SQL_DSN_USER", "t2s_reader"),
        "password": os.environ.get("T2SQL_READER_PASSWORD", ""),
    }


def run(sql: str, cfg: GuardConfig | None = None) -> ExecResult:
    if cfg is None:
        cfg = GuardConfig()
    conn: pg8000.native.Connection | None = None
    owned = False
    try:
        conn = pg8000.native.Connection(**_dsn())
        owned = True
        conn.run("BEGIN READ ONLY")
        conn.run(TIMEOUT_SQL)
        if cfg.dry_run:
            raw = conn.run(f"EXPLAIN (FORMAT JSON) {sql}")
            plan_row = raw[0][0] if raw else None
            if plan_row is None:
                return ExecResult(False, "DRYRUN_ERROR", "empty plan", sql, None)
            if isinstance(plan_row, str):
                plan_json = json.loads(plan_row)
            else:
                plan_json = plan_row
            try:
                summary = explain.evaluate(plan_json)
            except (ValueError, KeyError, TypeError) as exc:
                return ExecResult(False, "DRYRUN_ERROR", str(exc), sql, None)
            ok, code = explain.dry_run_verdict(summary)
            if not ok:
                return ExecResult(False, code, "", sql, None)
        fetched = conn.run(sql)
        rows: list[list[Any]] = [list(row) for row in fetched]
        payload = json.dumps(rows, default=str).encode("utf-8")
        if len(payload) > policy.MAX_RESULT_BYTES:
            return ExecResult(False, "RESULT_TOO_LARGE", str(len(payload)), sql, None)
        return ExecResult(True, "OK", "", sql, rows)
    except pg8000.native.Error as exc:
        sqlstate = getattr(exc, "sqlstate", None) or "XXXXX"
        if str(sqlstate) == "57014":
            return ExecResult(False, "EXEC_TIMEOUT", str(exc), sql, None)
        detail = f"{sqlstate} {exc}"
        return ExecResult(False, "DB_ERROR", detail, sql, None)
    except (OSError, ConnectionError) as exc:
        return ExecResult(False, "DB_UNAVAILABLE", str(exc), sql, None)
    finally:
        if conn is not None:
            try:
                conn.run("ROLLBACK")
            except pg8000.native.Error:
                pass
            if owned:
                conn.close()
