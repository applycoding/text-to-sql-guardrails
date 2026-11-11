# SPDX-License-Identifier: Apache-2.0
"""Verify built site-dist files match committed vendor pins."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VENDOR = ROOT / "site" / "vendor.json"
DEFAULT_SITE = ROOT / "site-dist" / "text-to-sql-guardrails"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def verify_site_dist(site_root: Path, vendor_path: Path) -> None:
    vendor = json.loads(vendor_path.read_text(encoding="utf-8"))
    site_files = vendor.get("site_files")
    if not site_files:
        raise SystemExit("committed vendor.json missing site_files pins")
    mismatches: list[str] = []
    for rel, expected in site_files.items():
        path = site_root / rel
        if not path.is_file():
            mismatches.append(f"{rel}: missing file")
            continue
        got = _sha256(path)
        if got != expected:
            mismatches.append(f"{rel}: got {got} expected {expected}")
    wheel = site_root / "sqlglot-30.31.0-py3-none-any.whl"
    wheel_expected = vendor["sqlglot_wheel"]["sha256"]
    if not wheel.is_file():
        mismatches.append("sqlglot wheel: missing file")
    else:
        got = _sha256(wheel)
        if got != wheel_expected:
            mismatches.append(f"sqlglot wheel: got {got} expected {wheel_expected}")
    if mismatches:
        raise SystemExit("site vendor pin mismatch:\n" + "\n".join(mismatches))


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    site_root = Path(args[0]) if args else DEFAULT_SITE
    vendor_path = Path(args[1]) if len(args) > 1 else DEFAULT_VENDOR
    verify_site_dist(site_root, vendor_path)
    print(f"site pins ok ({site_root})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
