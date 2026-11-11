# SPDX-License-Identifier: Apache-2.0
"""Verify NOTICE lists every locked dependency with version and license."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / "NOTICE"
REQS = [ROOT / "requirements.txt", ROOT / "requirements-dev.txt"]
WORKFLOWS = ROOT / ".github/workflows"

ACTION_LINE = re.compile(r"^\s{2}(actions/[\w-]+)\s+(v[\d.]+)\s+([0-9a-f]{40})\s+-\s+")
USES_LINE = re.compile(r"uses:\s*([^@\s]+)@([0-9a-f]{40})")


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


def _notice_pip_versions(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in text.splitlines():
        if "actions/" in line:
            continue
        match = re.match(r"^\s{2}([A-Za-z0-9_.-]+)\s+([^\s]+)\s+-\s+", line)
        if match:
            entries[match.group(1).lower()] = match.group(2)
    return entries


def _notice_actions(text: str) -> dict[str, tuple[str, str]]:
    actions: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        match = ACTION_LINE.match(line)
        if match:
            actions[match.group(1).lower()] = (match.group(2), match.group(3))
    return actions


def _workflow_action_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for wf in WORKFLOWS.glob("*.yml"):
        for line in wf.read_text(encoding="utf-8").splitlines():
            match = USES_LINE.search(line)
            if match:
                pins[match.group(1).lower()] = match.group(2)
    return pins


STATIC_OK = {
    "pyodide",
    "cpython",
    "emscripten",
    "chromium",
    "postgresql",
}


def main() -> int:
    notice_text = NOTICE.read_text(encoding="utf-8")
    notice_entries = _notice_pip_versions(notice_text)
    notice_actions = _notice_actions(notice_text)
    locked: dict[str, str] = {}
    for req in REQS:
        locked.update(_locked_versions(req))
    required = set(locked)
    missing = [name for name in sorted(required) if name not in notice_entries]
    extra = [
        name for name in sorted(notice_entries) if name not in required and name not in STATIC_OK
    ]
    wrong_version = [
        f"{name}: notice={notice_entries.get(name)} lock={locked[name]}"
        for name in sorted(required)
        if name in notice_entries and notice_entries[name] != locked[name]
    ]
    workflow_pins = _workflow_action_pins()
    action_mismatch: list[str] = []
    for action, sha in sorted(workflow_pins.items()):
        if action not in notice_actions:
            action_mismatch.append(f"missing in NOTICE: {action}")
            continue
        _version, notice_sha = notice_actions[action]
        if notice_sha != sha:
            action_mismatch.append(f"{action}: workflow={sha} notice={notice_sha}")
    for action in sorted(notice_actions):
        if action not in workflow_pins:
            action_mismatch.append(f"unused in workflows: {action}")

    if missing:
        print("NOTICE missing entries:", ", ".join(missing))
        return 1
    if extra:
        print("NOTICE extra entries:", ", ".join(extra))
        return 1
    if wrong_version:
        print("NOTICE version mismatch:", "; ".join(wrong_version))
        return 1
    if action_mismatch:
        print("NOTICE action pin mismatch:", "; ".join(action_mismatch))
        return 1
    print(f"NOTICE ok ({len(required)} pip packages, {len(notice_actions)} actions checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
