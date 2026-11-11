# SPDX-License-Identifier: Apache-2.0
"""Apply schema and role SQL as database admin."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pg8000.native

ROOT = Path(__file__).resolve().parents[2]


def _admin_conn() -> pg8000.native.Connection:
    return pg8000.native.Connection(
        host=os.environ.get("T2SQL_DSN_HOST", "localhost"),
        port=int(os.environ.get("T2SQL_DSN_PORT", "5432")),
        database=os.environ.get("T2SQL_DSN_DATABASE", "postgres"),
        user=os.environ.get("T2SQL_DSN_ADMIN_USER", "postgres"),
        password=os.environ.get(
            "T2SQL_DSN_ADMIN_PASSWORD",
            os.environ.get("POSTGRES_PASSWORD", ""),
        ),
    )


def _run_file(conn: pg8000.native.Connection, path: Path, substitutions: dict[str, str]) -> None:
    sql = path.read_text(encoding="utf-8")
    for key, value in substitutions.items():
        sql = sql.replace(key, value)
    conn.run(sql)


def seed() -> None:
    reader_password = os.environ.get("T2SQL_READER_PASSWORD", "ci_reader")
    db = os.environ.get("T2SQL_DSN_DATABASE", "postgres")
    conn = _admin_conn()
    try:
        _run_file(conn, ROOT / "sql" / "schema.sql", {})
        _run_file(
            conn,
            ROOT / "sql" / "roles.sql",
            {"<db>": f'"{db.replace(chr(34), chr(34) * 2)}"'},
        )
        escaped = reader_password.replace("'", "''")
        conn.run(f"ALTER ROLE t2s_reader WITH PASSWORD '{escaped}'")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    _ = parser.parse_args()
    seed()


if __name__ == "__main__":
    main()
