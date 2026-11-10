# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

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


def test_banner_and_basic_flow(http_server: str) -> None:
    requests_outside: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_request(req) -> None:
            if not req.url.startswith(http_server):
                requests_outside.append(req.url)

        page.on("request", on_request)
        page.goto(f"{http_server}/index.html", wait_until="networkidle", timeout=120_000)
        assert BANNER in page.content()
        page.click('button[data-q="top 3 products by revenue"]')
        page.click("#run")
        page.wait_for_timeout(5000)
        text = page.locator("#out").inner_text()
        payload = json.loads(text)
        assert payload["code"] == "OK"
        assert requests_outside == []
        browser.close()


def test_vendor_checksums() -> None:
    vendor = json.loads((ROOT / "site" / "vendor.json").read_text(encoding="utf-8"))
    assert vendor["pyodide"]["sha256"]
    assert vendor["sqlglot_wheel"]["sha256"]
