# SPDX-License-Identifier: Apache-2.0
"""Assemble static site with Pyodide and precomputed rows."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_SITE = ROOT / "site"
OUT_ROOT = ROOT / "site-dist"
OUT = OUT_ROOT / "text-to-sql-guardrails"
VENDOR = json.loads((SRC_SITE / "vendor.json").read_text(encoding="utf-8"))

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

PYODIDE_IGNORE = shutil.ignore_patterns("python.exe", "python.bat", "*.exe", "*.bat")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _download(url: str, expected: str) -> Path:
    tmp = Path(tempfile.mkstemp(suffix=".download")[1])
    urllib.request.urlretrieve(url, tmp)
    actual = _sha256(tmp)
    if actual != expected:
        raise SystemExit(f"checksum mismatch for {url}: {actual}")
    return tmp


def _copy_guard_sources(out_python: Path) -> None:
    mapping = {
        "guard.py": ROOT / "src/t2sql/guard.py",
        "policy.py": ROOT / "src/t2sql/policy.py",
        "model.py": ROOT / "src/t2sql/model.py",
    }
    for name, src in mapping.items():
        text = src.read_text(encoding="utf-8")
        text = text.replace("from t2sql import policy", "import policy")
        text = text.replace("from t2sql.policy import", "from policy import")
        out_python.mkdir(parents=True, exist_ok=True)
        (out_python / name).write_text(text, encoding="utf-8")


def _precomputed() -> dict[str, object]:
    from t2sql.model import StubModel
    from t2sql.pipeline import run_question
    from t2sql.seed import seed

    seed()
    model = StubModel()
    rows_map: dict[str, list[list[object]]] = {}
    schema = hashlib.sha256((ROOT / "sql" / "schema.sql").read_bytes()).hexdigest()
    questions = [
        "top 3 products by revenue",
        "how many customers in Denver?",
    ]
    for q in questions:
        result = run_question(model, q)
        if result.code != "OK" or result.sql is None:
            continue
        norm = q.strip().lower().rstrip("?").strip()
        key = "|".join([norm, result.sql, schema])
        rows_map[key] = result.rows or []
    return {"seed_hash": schema, "rows": rows_map}


def _corpus() -> dict[str, dict[str, str]]:
    from t2sql.guard import check
    from tests.test_attacks import ATTACKS

    return {case_id: {"sql": sql, "code": check(sql).code} for case_id, sql, *_ in ATTACKS}


def _read_sqlglot_license(whl_path: Path) -> str:
    with zipfile.ZipFile(whl_path, "r") as zf:
        for name in zf.namelist():
            if name.endswith("/LICENSE") or name.endswith("LICENSE.txt"):
                return zf.read(name).decode("utf-8", errors="replace")
    raise SystemExit("sqlglot license not found in wheel")


def _fetch_license_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _write_licenses(out: Path, whl_path: Path) -> None:
    licenses = out / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    (licenses / "sqlglot-MIT.txt").write_text(_read_sqlglot_license(whl_path), encoding="utf-8")
    tag = pyodide["version"] if (pyodide := VENDOR["pyodide"]).get("version") else "314.0.7"
    mpl = _fetch_license_text(f"https://raw.githubusercontent.com/pyodide/pyodide/{tag}/LICENSE")
    psf = _fetch_license_text("https://raw.githubusercontent.com/python/cpython/v3.14.0/LICENSE")
    (licenses / "pyodide-MPL-2.0.txt").write_text(mpl, encoding="utf-8")
    (licenses / "cpython-PSF-2.0.txt").write_text(psf, encoding="utf-8")


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT.mkdir(parents=True)

    pyodide = VENDOR["pyodide"]
    wheel = VENDOR["sqlglot_wheel"]
    archive = _download(pyodide["url"], pyodide["sha256"])
    whl = _download(wheel["url"], wheel["sha256"])

    with tempfile.TemporaryDirectory() as tmpdir:
        extract_root = Path(tmpdir)
        with tarfile.open(archive, "r:bz2") as tf:
            tf.extractall(extract_root, filter="data")
        nested = extract_root / "pyodide"
        if not nested.exists():
            raise SystemExit("missing pyodide directory in vendor archive")
        shutil.copytree(nested, OUT / "pyodide", dirs_exist_ok=True, ignore=PYODIDE_IGNORE)

    shutil.copy(whl, OUT / "sqlglot-30.31.0-py3-none-any.whl")
    for name in ("index.html", "style.css", "app.js"):
        shutil.copy(SRC_SITE / name, OUT / name)

    _copy_guard_sources(OUT / "python")
    _write_licenses(OUT, whl)
    (OUT / "precomputed.json").write_text(json.dumps(_precomputed(), default=str), encoding="utf-8")
    (OUT / "corpus_expected.json").write_text(json.dumps(_corpus()), encoding="utf-8")

    vendor_out = dict(VENDOR)
    vendor_out["site_files"] = {
        "pyodide/pyodide-lock.json": _sha256(OUT / "pyodide" / "pyodide-lock.json"),
        "pyodide/pyodide.js": _sha256(OUT / "pyodide" / "pyodide.js"),
        "sqlglot-30.31.0-py3-none-any.whl": _sha256(OUT / "sqlglot-30.31.0-py3-none-any.whl"),
    }
    (OUT / "vendor.json").write_text(json.dumps(vendor_out, indent=2) + "\n", encoding="utf-8")

    archive.unlink(missing_ok=True)
    whl.unlink(missing_ok=True)
    print(f"site built at {OUT}")


if __name__ == "__main__":
    main()
