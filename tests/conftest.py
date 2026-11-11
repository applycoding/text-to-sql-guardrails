# SPDX-License-Identifier: Apache-2.0
"""Pytest fixtures: database, network blocker, skip-is-failure."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from typing import Any

import pg8000.native
import pytest

ALLOWED_HOST = os.environ.get("T2SQL_DSN_HOST", "localhost")
ALLOWED_PORT = int(os.environ.get("T2SQL_DSN_PORT", "5432"))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    _ = config
    for item in items:
        if item.get_closest_marker("skip") is None:
            continue
        item.own_markers = [mark for mark in item.own_markers if mark.name != "skip"]

        def _fail() -> None:
            raise AssertionError("test skip is forbidden")

        item.obj = _fail


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]) -> Iterator[None]:
    outcome = yield
    rep = outcome.get_result()
    if rep.skipped:
        rep.outcome = "failed"
        rep.longrepr = "test skip is forbidden"
    if rep.passed and getattr(rep, "wasxfail", None):
        rep.outcome = "failed"


_real_connect = socket.socket.connect


def _guarded_connect(self: socket.socket, address: object) -> None:
    if isinstance(address, tuple) and len(address) >= 2:
        host, port = address[0], int(address[1])
        if host in ("127.0.0.1", "::1", ALLOWED_HOST) and port in (ALLOWED_PORT, 0):
            return _real_connect(self, address)
        raise OSError(f"outbound socket blocked: {host}:{port}")
    return _real_connect(self, address)


socket.socket.connect = _guarded_connect  # type: ignore[method-assign]


@pytest.fixture(scope="session")
def db_seeded() -> Iterator[None]:
    if os.environ.get("T2SQL_SKIP_DB") == "1":
        pytest.fail("database required")
    from t2sql.seed import seed

    seed()
    seed()
    yield


@pytest.fixture
def reader_conn(db_seeded: None) -> Iterator[pg8000.native.Connection]:
    conn = pg8000.native.Connection(
        host=ALLOWED_HOST,
        port=ALLOWED_PORT,
        database=os.environ.get("T2SQL_DSN_DATABASE", "postgres"),
        user="t2s_reader",
        password=os.environ.get("T2SQL_READER_PASSWORD", "ci_reader"),
    )
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def admin_conn(db_seeded: None) -> Iterator[pg8000.native.Connection]:
    conn = pg8000.native.Connection(
        host=ALLOWED_HOST,
        port=ALLOWED_PORT,
        database=os.environ.get("T2SQL_DSN_DATABASE", "postgres"),
        user=os.environ.get("T2SQL_DSN_ADMIN_USER", "postgres"),
        password=os.environ.get(
            "T2SQL_DSN_ADMIN_PASSWORD",
            os.environ.get("POSTGRES_PASSWORD", "ci_admin"),
        ),
    )
    try:
        yield conn
    finally:
        conn.close()
