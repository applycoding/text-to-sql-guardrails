# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pytest_skip_exits_nonzero_under_project_conftest() -> None:
    skip_body = """
import pytest

@pytest.mark.skip(reason="intentional skip probe")
def test_probe_skipped() -> None:
    pass
"""
    probe = ROOT / "tests" / "_probe_skip_once.py"
    try:
        probe.write_text(skip_body, encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                str(probe),
                "-q",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=env,
        )
        assert proc.returncode != 0
        assert "1 failed in" in proc.stdout
        assert " skipped in " not in proc.stdout
        assert " error in " not in proc.stdout
    finally:
        probe.unlink(missing_ok=True)
