# SPDX-License-Identifier: Apache-2.0
"""PLAN section 11 database-layer tests."""

from __future__ import annotations

import time

import pg8000.native
import pytest

CASES_RO = [
    ("email_col", "SELECT email FROM shop.customers", "42501"),
    ("staff", "SELECT * FROM shop.staff_salaries", "42501"),
    ("pg_authid", "SELECT * FROM pg_catalog.pg_authid", "42501"),
]

INSERT_SQL = "INSERT INTO shop.orders VALUES (99999, 1, '2025-01-01', 'x')"


def _sqlstate(exc: pg8000.native.Error) -> str:
    return str(getattr(exc, "sqlstate", None) or "XXXXX")


def _run_rw(conn: pg8000.native.Connection, sql: str) -> None:
    conn.run("COMMIT")
    conn.run("BEGIN")
    conn.run(sql)


@pytest.mark.parametrize(("case_id", "sql", "sqlstate"), CASES_RO)
def test_reader_denied(
    case_id: str, sql: str, sqlstate: str, reader_conn: pg8000.native.Connection
) -> None:
    _ = case_id
    with pytest.raises(pg8000.native.Error) as exc:
        reader_conn.run(sql)
    assert _sqlstate(exc.value) == sqlstate
    count = reader_conn.run("SELECT count(*) FROM shop.orders")[0][0]
    assert count == 8000


def test_insert_read_write_acl(reader_conn: pg8000.native.Connection) -> None:
    conn = reader_conn
    conn.run("COMMIT")
    conn.run("BEGIN")
    with pytest.raises(pg8000.native.Error) as exc:
        conn.run(INSERT_SQL)
    assert _sqlstate(exc.value) == "42501"


def test_insert_read_only(reader_conn: pg8000.native.Connection) -> None:
    conn = reader_conn
    conn.run("COMMIT")
    conn.run("BEGIN READ ONLY")
    with pytest.raises(pg8000.native.Error) as exc:
        conn.run(INSERT_SQL)
    assert _sqlstate(exc.value) == "25006"


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TEMP TABLE tt(x int)",
        "CREATE TABLE shop.x(a int)",
        "CREATE TABLE public.x(a int)",
    ],
)
def test_ddl_denied(sql: str, reader_conn: pg8000.native.Connection) -> None:
    conn = reader_conn
    conn.run("COMMIT")
    conn.run("BEGIN")
    with pytest.raises(pg8000.native.Error) as exc:
        conn.run(sql)
    assert _sqlstate(exc.value) == "42501"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_ls_dir('.')",
        "SELECT lo_import('/etc/passwd')",
    ],
)
def test_superuser_functions_denied(sql: str, reader_conn: pg8000.native.Connection) -> None:
    conn = reader_conn
    conn.run("COMMIT")
    conn.run("BEGIN")
    with pytest.raises(pg8000.native.Error) as exc:
        conn.run(sql)
    assert _sqlstate(exc.value) == "42501"


def test_statement_timeout_cancel(reader_conn: pg8000.native.Connection) -> None:
    conn = reader_conn
    start = time.monotonic()
    with pytest.raises(pg8000.native.Error) as exc:
        conn.run("SELECT pg_sleep(5)")
    elapsed = time.monotonic() - start
    assert _sqlstate(exc.value) == "57014"
    assert elapsed >= 1.5


def test_role_attributes(reader_conn: pg8000.native.Connection) -> None:
    row = reader_conn.run(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
        "rolbypassrls, (SELECT count(*) FROM pg_auth_members m "
        "WHERE m.member = r.oid) AS memberships, "
        "r.rolconfig FROM pg_roles r WHERE rolname = 't2s_reader'"
    )[0]
    assert row[0] is False
    assert row[1] is False
    assert row[2] is False
    assert row[3] is False
    assert row[4] is False
    assert row[5] == 0
    config = row[6] or []
    joined = " ".join(config)
    assert "search_path=pg_catalog, shop, pg_temp" in joined


def test_wrong_password(db_seeded: None) -> None:
    import os

    with pytest.raises(pg8000.native.Error) as exc:
        pg8000.native.Connection(
            host=os.environ.get("T2SQL_DSN_HOST", "localhost"),
            port=int(os.environ.get("T2SQL_DSN_PORT", "5432")),
            database=os.environ.get("T2SQL_DSN_DATABASE", "postgres"),
            user="t2s_reader",
            password="wrong-password",
        )
    assert _sqlstate(exc.value) == "28P01"


def test_orders_count_admin(admin_conn: pg8000.native.Connection) -> None:
    count = admin_conn.run("SELECT count(*) FROM shop.orders")[0][0]
    assert count == 8000
