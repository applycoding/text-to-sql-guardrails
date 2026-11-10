# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import subprocess
import sys

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
    proc = subprocess.run(
        [sys.executable, "-m", "t2sql", "check", "--sql", "SELECT 1"],
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
