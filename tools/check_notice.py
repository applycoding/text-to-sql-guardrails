# SPDX-License-Identifier: Apache-2.0
"""Verify NOTICE lists every locked dependency."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / "NOTICE"
REQS = [ROOT / "requirements.txt", ROOT / "requirements-dev.txt"]


def _packages(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and not line.startswith(" "):
            match = re.match(r"^([A-Za-z0-9_.-]+)==", line)
            if match:
                names.add(match.group(1).lower())
    return names


def main() -> int:
    notice_text = NOTICE.read_text(encoding="utf-8")
    locked: set[str] = set()
    for req in REQS:
        locked |= _packages(req)
    required = locked | {
        "pyodide",
        "cpython",
        "chromium",
        "postgresql",
        "github-actions",
    }
    missing = [name for name in sorted(required) if name not in notice_text.lower()]
    if missing:
        print("NOTICE missing entries:", ", ".join(missing))
        return 1
    print(f"NOTICE ok ({len(required)} packages checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
