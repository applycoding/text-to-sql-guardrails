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


def test_cli_ask_ok(db_seeded: None) -> None:
    proc = _run(["ask", "how many customers in Denver?"])
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["code"] == "OK"
    assert payload["rows"] == [[125]]


def test_cli_check_refusal() -> None:
    proc = _run(["check", "--sql", "SELECT pg_sleep(9)"])
    assert proc.returncode == 3
    payload = json.loads(proc.stdout)
    assert payload["code"] == "FUNCTION_NOT_ALLOWED"


def test_cli_run_dryrun_refusal(db_seeded: None) -> None:
    proc = _run(
        [
            "run",
            "--sql",
            "SELECT o.id FROM orders o, order_items i",
        ]
    )
    assert proc.returncode == 3
    assert json.loads(proc.stdout)["code"] == "DRYRUN_ROWS"


def test_cli_bad_model() -> None:
    proc = _run(["ask", "hello"], {"T2SQL_MODEL": "invalid"})
    assert proc.returncode == 2
