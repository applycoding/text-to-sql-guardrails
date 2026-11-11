# SPDX-License-Identifier: Apache-2.0
"""Verify NOTICE lists every locked dependency with version and license."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / "NOTICE"
REQS = [ROOT / "requirements.txt", ROOT / "requirements-dev.txt"]


def _locked_versions(path: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and not line.startswith(" "):
            line = line.rstrip()
            if line.endswith("\\"):
                line = line[:-1].rstrip()
            match = re.match(r"^([A-Za-z0-9_.-]+)==(.+)$", line)
            if match:
                names[match.group(1).lower()] = match.group(2).strip()
    return names


def _notice_versions(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s{2}([A-Za-z0-9_./-]+)\s+([^\s]+)\s+-\s+", line)
        if match:
            entries[match.group(1).lower()] = match.group(2)
    return entries


STATIC_OK = {
    "pyodide",
    "cpython",
    "emscripten",
    "chromium",
    "postgresql",
    "actions/checkout",
    "actions/setup-python",
    "actions/upload-artifact",
    "actions/download-artifact",
    "actions/configure-pages",
    "actions/upload-pages-artifact",
    "actions/deploy-pages",
}


def main() -> int:
    notice_text = NOTICE.read_text(encoding="utf-8")
    notice_entries = _notice_versions(notice_text)
    locked: dict[str, str] = {}
    for req in REQS:
        locked.update(_locked_versions(req))
    required = set(locked)
    missing = [name for name in sorted(required) if name not in notice_entries]
    extra = [
        name
        for name in sorted(notice_entries)
        if name not in required and name not in STATIC_OK
    ]
    wrong_version = [
        f"{name}: notice={notice_entries.get(name)} lock={locked[name]}"
        for name in sorted(required)
        if name in notice_entries and notice_entries[name] != locked[name]
    ]
    if missing:
        print("NOTICE missing entries:", ", ".join(missing))
        return 1
    if extra:
        print("NOTICE extra entries:", ", ".join(extra))
        return 1
    if wrong_version:
        print("NOTICE version mismatch:", "; ".join(wrong_version))
        return 1
    print(f"NOTICE ok ({len(required)} pip packages checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
