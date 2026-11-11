# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site-dist"

BANNER = "demo, deterministic offline model, not a production security boundary"


@pytest.fixture(scope="module")
def http_server() -> str:
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", "8765", "--directory", str(SITE)],
        cwd=ROOT,
    )
    time.sleep(1)
    yield "http://127.0.0.1:8765"
    proc.terminate()
    proc.wait(timeout=10)


def _wait_boot(page: Page) -> None:
    page.wait_for_function(
        "() => window.pyodideBoot === 'ready' || window.pyodideBoot === 'error'",
        timeout=180_000,
    )
    if page.evaluate("() => window.pyodideBoot") == "error":
        text = page.locator("#out").inner_text()
        raise AssertionError(f"pyodide boot failed: {text}")


def _open_page(page: Page, http_server: str) -> None:
    page.goto(f"{http_server}/index.html", wait_until="networkidle", timeout=120_000)
    assert BANNER in page.content()
    _wait_boot(page)


def _run_guard(page: Page) -> dict:
    page.click("#run")
    page.wait_for_function(
        "() => (document.querySelector('#out')?.textContent || '').includes('\"code\"')",
        timeout=60_000,
    )
    return json.loads(page.locator("#out").inner_text())


@pytest.mark.timeout(300)
def test_banner_and_basic_flow(http_server: str) -> None:
    requests_outside: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_request(req) -> None:
            if not req.url.startswith(http_server):
                requests_outside.append(req.url)

        page.on("request", on_request)
        _open_page(page, http_server)
        page.click('button[data-q="top 3 products by revenue"]')
        payload = _run_guard(page)
        assert payload.get("code") == "OK", payload
        assert payload.get("sql")
        rows = payload.get("rows")
        assert isinstance(rows, list)
        assert len(rows) == 3
        assert requests_outside == []
        browser.close()


@pytest.mark.timeout(180)
def test_pg_sleep_refused(http_server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        _open_page(page, http_server)
        page.click('button[data-q="SELECT pg_sleep(9)"]')
        payload = _run_guard(page)
        assert payload.get("code") == "FUNCTION_NOT_ALLOWED", payload
        browser.close()


@pytest.mark.timeout(180)
def test_no_template(http_server: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        _open_page(page, http_server)
        page.click('button[data-q="how many customers in atlantis"]')
        payload = _run_guard(page)
        assert payload.get("code") == "NO_TEMPLATE", payload
        browser.close()


@pytest.mark.timeout(600)
def test_corpus_parity_with_cpython(http_server: str) -> None:
    expected_path = SITE / "corpus_expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        _open_page(page, http_server)
        actual = page.evaluate("() => window.runCorpusCheck()")
        mismatches = []
        for case_id, entry in expected.items():
            want = entry["code"]
            got = actual[case_id]
            if got != want:
                mismatches.append(f"{case_id}: browser={got} python={want}")
        browser.close()
    assert mismatches == [], "\n".join(mismatches)


def test_vendor_checksums() -> None:
    vendor = json.loads((ROOT / "site" / "vendor.json").read_text(encoding="utf-8"))
    assert vendor["pyodide"]["sha256"]
    assert vendor["sqlglot_wheel"]["sha256"]
