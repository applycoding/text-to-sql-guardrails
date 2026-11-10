# SPDX-License-Identifier: Apache-2.0
"""Command-line interface for t2sql."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from t2sql.guard import check
from t2sql.model import make_model
from t2sql.pipeline import run_question, run_sql


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="t2sql")
    sub = parser.add_subparsers(dest="command", required=True)

    ask_p = sub.add_parser("ask")
    ask_p.add_argument("question")

    check_p = sub.add_parser("check")
    check_p.add_argument("--sql", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--sql", required=True)

    args = parser.parse_args(argv)
    if args.command == "ask":
        try:
            model = make_model()
        except SystemExit:
            return 2
        result = run_question(model, args.question)
        payload = {
            "code": result.code,
            "detail": result.detail,
            "sql": result.sql,
            "rows": result.rows,
        }
        _emit(payload)
        return 0 if result.code == "OK" else 3

    if args.command == "check":
        verdict = check(args.sql)
        payload = {
            "code": verdict.code,
            "detail": verdict.detail,
            "sql": verdict.sql,
            "rows": None,
        }
        _emit(payload)
        if verdict.code == "DB_UNAVAILABLE":
            return 4
        return 0 if verdict.ok else 3

    if args.command == "run":
        result = run_sql(args.sql)
        payload = {
            "code": result.code,
            "detail": result.detail,
            "sql": result.sql,
            "rows": result.rows,
        }
        _emit(payload)
        if result.code == "DB_UNAVAILABLE":
            return 4
        return 0 if result.code == "OK" else 3

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
