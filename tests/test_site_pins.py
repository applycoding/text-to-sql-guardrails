# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify_site_pins.py"


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _write_vendor(vendor_path: Path, js: bytes, lock: bytes, wheel: bytes) -> None:
    vendor = {
        "pyodide": {"version": "0"},
        "sqlglot_wheel": {"sha256": _sha256_bytes(wheel)},
        "site_files": {
            "pyodide/pyodide.js": _sha256_bytes(js),
            "pyodide/pyodide-lock.json": _sha256_bytes(lock),
        },
    }
    vendor_path.write_text(json.dumps(vendor, indent=2), encoding="utf-8")


def _run_verify(site_root: Path, vendor_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFY), str(site_root), str(vendor_path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def _fresh_tree() -> tuple[Path, Path, Path]:
    tmp = Path(tempfile.mkdtemp())
    site = tmp / "site"
    vendor_path = tmp / "vendor.json"
    js = b"pin-test-js-v1"
    lock = b'{"packages": {}}'
    wheel = b"pin-test-wheel-bytes"
    (site / "pyodide").mkdir(parents=True)
    (site / "pyodide" / "pyodide.js").write_bytes(js)
    (site / "pyodide" / "pyodide-lock.json").write_bytes(lock)
    (site / "sqlglot-30.31.0-py3-none-any.whl").write_bytes(wheel)
    _write_vendor(vendor_path, js, lock, wheel)
    return site, vendor_path, tmp


def test_verify_site_pins_accepts_clean_tree() -> None:
    site, vendor_path, tmp = _fresh_tree()
    try:
        proc = _run_verify(site, vendor_path)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "site pins ok" in proc.stdout
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_verify_site_pins_rejects_tampered_pyodide_js() -> None:
    site, vendor_path, tmp = _fresh_tree()
    try:
        js = site / "pyodide" / "pyodide.js"
        js.write_bytes(js.read_bytes() + b"tamper")
        proc = _run_verify(site, vendor_path)
        assert proc.returncode != 0
        assert "pyodide/pyodide.js" in proc.stdout + proc.stderr
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_verify_site_pins_rejects_tampered_pyodide_lock() -> None:
    site, vendor_path, tmp = _fresh_tree()
    try:
        lock = site / "pyodide" / "pyodide-lock.json"
        lock.write_bytes(lock.read_bytes() + b"tamper")
        proc = _run_verify(site, vendor_path)
        assert proc.returncode != 0
        assert "pyodide/pyodide-lock.json" in proc.stdout + proc.stderr
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_verify_site_pins_rejects_missing_pyodide_js() -> None:
    site, vendor_path, tmp = _fresh_tree()
    try:
        (site / "pyodide" / "pyodide.js").unlink()
        proc = _run_verify(site, vendor_path)
        assert proc.returncode != 0
        assert "missing file" in proc.stdout + proc.stderr
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
