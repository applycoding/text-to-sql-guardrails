# SPDX-License-Identifier: Apache-2.0
"""Assemble static site with Pyodide and precomputed rows."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_SITE = ROOT / "site"
OUT = ROOT / "site-dist"
VENDOR = json.loads((SRC_SITE / "vendor.json").read_text(encoding="utf-8"))

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _download(url: str, dest: Path, expected: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    actual = _sha256(dest)
    if actual != expected:
        raise SystemExit(f"checksum mismatch for {dest.name}: {actual}")


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
        norm = q.strip().lower()
        key = "|".join([norm, result.sql, schema])
        rows_map[key] = result.rows or []
    return {"seed_hash": schema, "rows": rows_map}


def _corpus() -> dict[str, dict[str, str]]:
    from t2sql.guard import check
    from tests.test_attacks import ATTACKS

    return {case_id: {"sql": sql, "code": check(sql).code} for case_id, sql, *_ in ATTACKS}


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    pyodide = VENDOR["pyodide"]
    wheel = VENDOR["sqlglot_wheel"]
    archive = OUT / "vendor" / "pyodide-core.tar.bz2"
    whl = OUT / "vendor" / "sqlglot.whl"
    _download(pyodide["url"], archive, pyodide["sha256"])
    _download(wheel["url"], whl, wheel["sha256"])

    extract_root = OUT / "vendor_extract"
    extract_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:bz2") as tf:
        tf.extractall(extract_root, filter="data")
    pyodide_dir = OUT / "pyodide"
    nested = extract_root / "pyodide"
    if nested.exists():
        shutil.copytree(nested, pyodide_dir, dirs_exist_ok=True)
    else:
        raise SystemExit("missing pyodide directory in vendor archive")
    shutil.copy(whl, OUT / "sqlglot-30.31.0-py3-none-any.whl")
    for name in ("index.html", "style.css", "app.js", "vendor.json"):
        shutil.copy(SRC_SITE / name, OUT / name)

    _copy_guard_sources(OUT / "python")
    (OUT / "precomputed.json").write_text(json.dumps(_precomputed(), default=str), encoding="utf-8")
    (OUT / "corpus_expected.json").write_text(json.dumps(_corpus()), encoding="utf-8")
    print(f"site built at {OUT}")


if __name__ == "__main__":
    main()
