# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify_site_pins.py"
COMMITTED_VENDOR = ROOT / "site" / "vendor.json"
SITE = ROOT / "site-dist" / "text-to-sql-guardrails"


@pytest.mark.skipif(not SITE.is_dir(), reason="site-dist not built")
def test_verify_site_pins_rejects_tampered_pyodide_js() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        copy_root = Path(tmpdir) / "copy"
        shutil.copytree(SITE, copy_root)
        js = copy_root / "pyodide" / "pyodide.js"
        js.write_bytes(js.read_bytes() + b"\n")
        proc = subprocess.run(
            [sys.executable, str(VERIFY), str(copy_root), str(COMMITTED_VENDOR)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert proc.returncode != 0
        assert "pin mismatch" in proc.stdout + proc.stderr
