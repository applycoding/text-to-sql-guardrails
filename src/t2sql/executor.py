# SPDX-License-Identifier: Apache-2.0
"""PostgreSQL executor: dry run and read-only execution."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import pg8000.native
from pg8000.exceptions import InterfaceError

from t2sql import explain, policy
from t2sql.guard import GuardConfig

TIMEOUT_SQL = f"SET LOCAL statement_timeout = '{policy.STATEMENT_TIMEOUT_MS // 1000}s'"

RUN_COUNT = 0
LAST_SQL: str | None = None


@dataclass(frozen=True)
class ExecResult:
    ok: bool
    code: str
    detail: str
    sql: str | None
    rows: list[list[Any]] | None


def _dsn() -> dict[str, Any]:
    return {
        "host": os.environ.get("T2SQL_DSN_HOST", "localhost"),
        "port": int(os.environ.get("T2SQL_DSN_PORT", "5432")),
        "database": os.environ.get("T2SQL_DSN_DATABASE", "postgres"),
        "user": os.environ.get("T2SQL_DSN_USER", "t2s_reader"),
        "password": os.environ.get("T2SQL_READER_PASSWORD", ""),
    }


def _sqlstate_and_message(exc: pg8000.native.Error) -> tuple[str, str]:
    if exc.args and isinstance(exc.args[0], dict):
        payload = exc.args[0]
        state = str(payload.get("C", "XXXXX"))
        msg = str(payload.get("M", exc))
        return state, msg
    state = str(getattr(exc, "sqlstate", None) or "XXXXX")
    return state, str(exc)


def run(sql: str, cfg: GuardConfig | None = None) -> ExecResult:
    global RUN_COUNT, LAST_SQL
    if cfg is None:
        cfg = GuardConfig()
    RUN_COUNT += 1
    LAST_SQL = sql
    conn: pg8000.native.Connection | None = None
    try:
        conn = pg8000.native.Connection(**_dsn())
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
        rows: list[list[Any]] = []
        for row in fetched:
            normalized: list[Any] = []
            for cell in row:
                if hasattr(cell, "isoformat"):
                    normalized.append(cell.isoformat())
                else:
                    normalized.append(cell)
            rows.append(normalized)
        payload = json.dumps(rows, default=str).encode("utf-8")
        if len(payload) > policy.MAX_RESULT_BYTES:
            return ExecResult(False, "RESULT_TOO_LARGE", str(len(payload)), sql, None)
        return ExecResult(True, "OK", "", sql, rows)
    except InterfaceError as exc:
        return ExecResult(False, "DB_UNAVAILABLE", str(exc), sql, None)
    except (OSError, ConnectionError) as exc:
        return ExecResult(False, "DB_UNAVAILABLE", str(exc), sql, None)
    except pg8000.native.Error as exc:
        sqlstate, message = _sqlstate_and_message(exc)
        if sqlstate == "57014":
            return ExecResult(False, "EXEC_TIMEOUT", f"{sqlstate} {message}", sql, None)
        return ExecResult(False, "DB_ERROR", f"{sqlstate} {message}", sql, None)
    finally:
        if conn is not None:
            try:
                conn.run("ROLLBACK")
            except pg8000.native.Error:
                pass
            conn.close()
