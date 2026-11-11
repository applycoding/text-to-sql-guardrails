# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from t2sql.model import StubModel, make_model


def test_factory_default_stub() -> None:
    old = os.environ.pop("T2SQL_MODEL", None)
    try:
        model = make_model()
        assert isinstance(model, StubModel)
    finally:
        if old is not None:
            os.environ["T2SQL_MODEL"] = old


def test_unknown_model_exits_2() -> None:
    env = {**os.environ, "T2SQL_MODEL": "not-a-model"}
    env.pop("T2SQL_MODEL", None)
    env["T2SQL_MODEL"] = "not-a-model"
    proc = subprocess.run(
        [sys.executable, "-m", "t2sql", "ask", "hello"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert proc.returncode == 2


def test_openai_adapter_missing_env_exits_2() -> None:
    env = os.environ.copy()
    env["T2SQL_MODEL"] = "openai-compatible"
    env.pop("T2SQL_LLM_BASE_URL", None)
    proc = subprocess.run(
        [sys.executable, "-m", "t2sql", "ask", "hello"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert proc.returncode == 2


def test_stub_no_network_calls() -> None:
    model = StubModel()
    assert model.to_sql("how many customers in Denver?") is not None


def test_socket_guard_blocks_other_hosts() -> None:
    import socket

    with pytest.raises(OSError):
        socket.create_connection(("93.184.216.34", 80), timeout=1)


def test_openai_adapter_to_sql_blocked() -> None:
    import urllib.request

    os.environ["T2SQL_MODEL"] = "openai-compatible"
    os.environ["T2SQL_LLM_BASE_URL"] = "http://93.184.216.34"
    os.environ["T2SQL_LLM_API_KEY"] = "x"
    os.environ["T2SQL_LLM_MODEL"] = "x"
    from t2sql.adapters.openai_compat import OpenAICompatModel

    with pytest.raises(OSError):
        urllib.request.urlopen(
            urllib.request.Request(
                "http://93.184.216.34/v1/chat/completions",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=1,
        )
    model = OpenAICompatModel()
    assert model.to_sql("hello") is None
