# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))


def _run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "t2sql", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=merged,
    )


def _one_json(stdout: str) -> dict:
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    return json.loads(lines[0])


def test_cli_ask_ok(db_seeded: None) -> None:
    proc = _run(["ask", "how many customers in Denver?"])
    assert proc.returncode == 0
    payload = _one_json(proc.stdout)
    assert payload["code"] == "OK"
    assert payload["rows"] == [[125]]


def test_cli_check_guard_refusal() -> None:
    proc = _run(["check", "--sql", "SELECT pg_sleep(9)"])
    assert proc.returncode == 3
    assert _one_json(proc.stdout)["code"] == "FUNCTION_NOT_ALLOWED"


def test_cli_run_dryrun_refusal(db_seeded: None) -> None:
    proc = _run(["run", "--sql", "SELECT o.id FROM orders o, order_items i"])
    assert proc.returncode == 3
    assert _one_json(proc.stdout)["code"] == "DRYRUN_ROWS"


def test_cli_run_ok_single_json(db_seeded: None) -> None:
    proc = _run(["run", "--sql", "SELECT 1"])
    assert proc.returncode == 0
    assert _one_json(proc.stdout)["code"] == "OK"


def test_cli_run_db_unavailable() -> None:
    proc = _run(["run", "--sql", "SELECT 1"], {"T2SQL_DSN_PORT": "1"})
    assert proc.returncode == 4
    assert _one_json(proc.stdout)["code"] == "DB_UNAVAILABLE"


def test_cli_ask_db_unavailable() -> None:
    proc = _run(["ask", "how many customers in Denver?"], {"T2SQL_DSN_PORT": "1"})
    assert proc.returncode == 4
    assert _one_json(proc.stdout)["code"] == "DB_UNAVAILABLE"


def test_cli_usage_error() -> None:
    proc = _run(["check"])
    assert proc.returncode == 2
    assert proc.stdout == ""


def test_cli_bad_model_stderr() -> None:
    proc = _run(["ask", "hello"], {"T2SQL_MODEL": "invalid"})
    assert proc.returncode == 2
    assert "unknown T2SQL_MODEL" in proc.stderr


_TIMEOUT_SQL = (
    "SELECT sum(o1.id::numeric * o2.id::numeric) "
    "FROM orders o1, orders o2, orders o3, order_items i"
)


def test_cli_run_db_error(db_seeded: None) -> None:
    proc = _run(["run", "--sql", "SELECT 1/0"])
    assert proc.returncode == 3
    payload = _one_json(proc.stdout)
    assert payload["code"] == "DB_ERROR"
    assert payload["detail"].startswith("22012 ")


def test_cli_run_exec_timeout(db_seeded: None) -> None:
    proc = _run(["run", "--sql", _TIMEOUT_SQL], {"T2SQL_DRY_RUN": "0"})
    assert proc.returncode == 3
    payload = _one_json(proc.stdout)
    assert payload["code"] == "EXEC_TIMEOUT"
    assert payload["detail"].startswith("57014 ")
