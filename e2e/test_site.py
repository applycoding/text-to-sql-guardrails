# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = ROOT / "site-dist"
SITE = SITE_ROOT / "text-to-sql-guardrails"
BASE_PATH = "/text-to-sql-guardrails"

BANNER = "demo, deterministic offline model, not a production security boundary"
NOTE = "AST checks ran in your browser; database checks ran in CI"

TOP3_GOLD = [
    ["Product 84", 6454206],
    ["Product 80", 6171652],
    ["Product 76", 5852142],
]


@pytest.fixture(scope="module")
def http_server() -> str:
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", "8765", "--directory", str(SITE_ROOT)],
        cwd=ROOT,
    )
    time.sleep(1)
    yield "http://127.0.0.1:8765"
    proc.terminate()
    proc.wait(timeout=10)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _track_external(page: Page, http_server: str) -> list[str]:
    outside: list[str] = []

    def on_request(req) -> None:
        if not req.url.startswith(http_server):
            outside.append(req.url)

    page.on("request", on_request)
    return outside


def _wait_boot(page: Page) -> None:
    page.wait_for_function(
        "() => window.pyodideBoot === 'ready' || window.pyodideBoot === 'error'",
        timeout=180_000,
    )
    if page.evaluate("() => window.pyodideBoot") == "error":
        text = page.locator("#out").inner_text()
        raise AssertionError(f"pyodide boot failed: {text}")


def _open_page(page: Page, http_server: str) -> list[str]:
    outside = _track_external(page, http_server)
    page.goto(f"{http_server}{BASE_PATH}/index.html", wait_until="networkidle", timeout=120_000)
    assert BANNER in page.content()
    assert page.title() == BANNER
    _wait_boot(page)
    return outside


def _run_guard(page: Page) -> dict:
    page.click("#run")
    page.wait_for_function(
        "() => (document.querySelector('#out')?.textContent || '').includes('\"code\"')",
        timeout=60_000,
    )
    return json.loads(page.locator("#out").inner_text())


@pytest.mark.timeout(300)
def test_banner_and_basic_flow(http_server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        outside = _open_page(page, http_server)
        page.click('button[data-q="top 3 products by revenue"]')
        payload = _run_guard(page)
        assert payload.get("code") == "OK", payload
        assert payload.get("note") == NOTE
        assert payload.get("sql")
        rows = payload.get("rows")
        assert rows is not None
        assert rows == TOP3_GOLD
        assert outside == []
        browser.close()


@pytest.mark.timeout(180)
def test_pg_sleep_refused(http_server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        outside = _open_page(page, http_server)
        page.click('button[data-q="SELECT pg_sleep(9)"]')
        payload = _run_guard(page)
        assert payload.get("code") == "FUNCTION_NOT_ALLOWED", payload
        assert outside == []
        browser.close()


@pytest.mark.timeout(180)
def test_no_template(http_server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        outside = _open_page(page, http_server)
        page.click('button[data-q="how many customers in atlantis"]')
        payload = _run_guard(page)
        assert payload.get("code") == "NO_TEMPLATE", payload
        assert outside == []
        browser.close()


@pytest.mark.timeout(600)
def test_corpus_parity_with_cpython(http_server: str) -> None:
    expected_path = SITE / "corpus_expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        outside = _open_page(page, http_server)
        actual = page.evaluate("() => window.runCorpusCheck()")
        mismatches = []
        for case_id, entry in expected.items():
            want = entry["code"]
            got = actual[case_id]
            if got != want:
                mismatches.append(f"{case_id}: browser={got} python={want}")
        assert outside == []
        browser.close()
    assert mismatches == [], "\n".join(mismatches)


COMMITTED_VENDOR = ROOT / "site" / "vendor.json"


def test_vendor_checksums() -> None:
    vendor = json.loads(COMMITTED_VENDOR.read_text(encoding="utf-8"))
    expected = vendor["site_files"]
    assert _sha256(SITE / "pyodide" / "pyodide-lock.json") == expected["pyodide/pyodide-lock.json"]
    assert _sha256(SITE / "pyodide" / "pyodide.js") == expected["pyodide/pyodide.js"]
    wheel = SITE / "sqlglot-30.31.0-py3-none-any.whl"
    assert _sha256(wheel) == vendor["sqlglot_wheel"]["sha256"]


def test_vendor_pin_verification_rejects_tamper() -> None:
    import shutil
    import subprocess
    import sys
    import tempfile

    verify = ROOT / "tools" / "verify_site_pins.py"
    with tempfile.TemporaryDirectory() as tmpdir:
        copy_root = Path(tmpdir) / "copy"
        shutil.copytree(SITE, copy_root)
        js = copy_root / "pyodide" / "pyodide.js"
        js.write_bytes(js.read_bytes() + b"\n")
        proc = subprocess.run(
            [sys.executable, str(verify), str(copy_root), str(COMMITTED_VENDOR)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert proc.returncode != 0
        assert "pin mismatch" in proc.stdout + proc.stderr


def test_site_has_no_windows_launchers() -> None:
    for path in SITE.rglob("*"):
        if path.is_file():
            assert path.suffix.lower() not in {".exe", ".bat"}, path
