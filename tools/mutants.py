# SPDX-License-Identifier: Apache-2.0
"""Apply one source patch at a time and run mutant target tests."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Patch:
    path: str
    search: str
    replace: str


@dataclass(frozen=True)
class Mutant:
    mutant_id: str
    patches: tuple[Patch, ...]
    target_test: str


MUTANTS: list[Mutant] = [
    Mutant(
        "M1",
        (
            Patch(
                "src/t2sql/guard.py",
                '    if cfg.single_statement and len(statements) > 1:\n        return _refuse("MULTI_STATEMENT", str(len(statements)))\n',
                "",
            ),
        ),
        "tests/test_mutant_targets.py::test_m1_stacked",
    ),
    Mutant(
        "M2",
        (
            Patch(
                "src/t2sql/guard.py",
                "    if cfg.statement_type:\n"
                "        if type(tree) not in policy.ALLOWED_ROOT_TYPES:\n"
                '            return _refuse("STATEMENT_NOT_ALLOWED", type(tree).__name__)\n'
                "        forb = _forbidden_nodes(tree)\n"
                "        if forb is not None:\n"
                '            return _refuse("STATEMENT_NOT_ALLOWED", type(forb).__name__)\n',
                "    if cfg.statement_type:\n"
                "        if type(tree) not in policy.ALLOWED_ROOT_TYPES and type(tree) is not exp.Command:\n"
                '            return _refuse("STATEMENT_NOT_ALLOWED", type(tree).__name__)\n'
                "        forb = None if type(tree) is exp.Command else _forbidden_nodes(tree)\n"
                "        if forb is not None:\n"
                '            return _refuse("STATEMENT_NOT_ALLOWED", type(forb).__name__)\n',
            ),
        ),
        "tests/test_mutant_targets.py::test_m2_do_block",
    ),
    Mutant(
        "M3",
        (
            Patch(
                "src/t2sql/guard.py",
                '    shadow = cte_names & policy.ALLOWED_TABLES\n    if shadow:\n        return _refuse("CTE_SHADOWS_TABLE", f"CTE shadows table: {sorted(shadow)[0]}")\n',
                "",
            ),
        ),
        "tests/test_mutant_targets.py::test_m3_cte_shadow",
    ),
    Mutant(
        "M4",
        (
            Patch(
                "src/t2sql/guard.py",
                "            if schema_part:\n"
                "                if schema_quoted:\n"
                "                    schema_ok = schema_part == policy.ALLOWED_SCHEMA\n"
                "                else:\n"
                "                    schema_ok = schema_part.lower() == policy.ALLOWED_SCHEMA\n"
                "                if not schema_ok:\n"
                '                    return _refuse("TABLE_NOT_ALLOWED", f"{schema_part}.{name}")\n',
                "",
            ),
        ),
        "tests/test_mutant_targets.py::test_m4_public_orders",
    ),
    Mutant(
        "M5",
        (
            Patch(
                "src/t2sql/guard.py",
                "            if isinstance(child.this, (exp.Anonymous, exp.ExplodingGenerateSeries)):\n"
                '                return _refuse("FUNCTION_NOT_ALLOWED", "function relation")\n',
                "            if isinstance(child.this, (exp.Anonymous, exp.ExplodingGenerateSeries)):\n"
                "                continue\n",
            ),
            Patch(
                "src/t2sql/guard.py",
                "def _check_nodes(node: exp.Expression) -> Verdict | None:\n"
                "    for child in node.walk():\n"
                "        cls = type(child)\n",
                "def _check_nodes(node: exp.Expression) -> Verdict | None:\n"
                "    for child in node.walk():\n"
                "        parent = child.parent\n"
                "        while parent is not None and not isinstance(parent, exp.Table):\n"
                "            parent = parent.parent\n"
                "        if parent is not None:\n"
                "            continue\n"
                "        cls = type(child)\n",
            ),
        ),
        "tests/test_mutant_targets.py::test_m5_dblink_from",
    ),
    Mutant(
        "M6",
        (
            Patch(
                "src/t2sql/policy.py",
                '    "customers": frozenset({"id", "name", "city", "signup_date"}),\n',
                '    "customers": frozenset({"id", "name", "city", "signup_date", "email"}),\n',
            ),
        ),
        "tests/test_mutant_targets.py::test_m6_email",
    ),
    Mutant(
        "M7",
        (
            Patch(
                "src/t2sql/guard.py",
                "            if val > policy.MAX_LIMIT:\n"
                '                sel.set("limit", exp.Limit(expression=exp.Literal.number(policy.MAX_LIMIT)))\n',
                "",
            ),
        ),
        "tests/test_mutant_targets.py::test_m7_limit_clamp",
    ),
    Mutant(
        "M8",
        (
            Patch(
                "src/t2sql/guard.py",
                "    whole = _whole_row_refs(node)\n    if whole:\n        return whole\n",
                "",
            ),
        ),
        "tests/test_mutant_targets.py::test_m8_whole_row",
    ),
    Mutant(
        "M9",
        (
            Patch(
                "src/t2sql/explain.py",
                "    for node in _walk_plans(root):\n"
                '        if "Plan Rows" not in node:\n'
                '            raise ValueError("missing Plan Rows")\n'
                '        if "Total Cost" not in node:\n'
                '            raise ValueError("missing Total Cost")\n'
                '        max_rows = max(max_rows, float(node["Plan Rows"]))\n',
                '    max_rows = float(root["Plan Rows"])\n',
            ),
        ),
        "tests/test_mutant_targets.py::test_m9_dryrun_rows",
    ),
    Mutant(
        "M10",
        (
            Patch(
                "src/t2sql/explain.py",
                '    if summary.total_cost > policy.MAX_PLAN_COST:\n        return False, "DRYRUN_COST"\n',
                "",
            ),
        ),
        "tests/test_mutant_targets.py::test_m10_synthetic_cost",
    ),
    Mutant(
        "M11",
        (
            Patch(
                "src/t2sql/guard.py",
                "        if isinstance(child, exp.Cast):\n"
                "            if child.to and not _is_allowed_cast(child.to):\n"
                '                return _refuse("CAST_NOT_ALLOWED", child.to.sql())\n'
                "        if isinstance(child, exp.DataType):\n"
                "            parent = child.parent\n"
                "            if parent and isinstance(parent, exp.Cast):\n"
                "                if not _is_allowed_cast(child):\n"
                '                    return _refuse("CAST_NOT_ALLOWED", child.sql())\n'
                "            continue\n",
                "        if isinstance(child, exp.DataType):\n            continue\n",
            ),
        ),
        "tests/test_mutant_targets.py::test_m11_regclass_cast",
    ),
    Mutant(
        "M12",
        (
            Patch(
                "src/t2sql/guard.py",
                "        if isinstance(child, (exp.Binary, exp.Unary)) and cls not in policy.STRUCTURAL_NODES:\n"
                '            return _refuse("FUNCTION_NOT_ALLOWED", cls.__name__)\n'
                "        if isinstance(child, exp.Anonymous):\n"
                '            return _refuse("FUNCTION_NOT_ALLOWED", child.name or cls.__name__)\n'
                "        refuse_types = (\n"
                "            exp.Window,\n"
                "            exp.Filter,\n"
                "            exp.Lateral,\n"
                "            exp.Values,\n"
                "            exp.TableSample,\n"
                "            exp.Fetch,\n"
                "            exp.RawString,\n"
                "            exp.UnicodeString,\n"
                "            exp.ByteString,\n"
                "        )\n"
                "        for rt in refuse_types:\n"
                "            if isinstance(child, rt):\n"
                '                return _refuse("UNSUPPORTED_SYNTAX", cls.__name__)\n'
                "        extra_refuse = (\n"
                '            "CurrentVersion",\n'
                '            "Explode",\n'
                '            "ExplodingGenerateSeries",\n'
                '            "Rand",\n'
                '            "Repeat",\n'
                '            "Pad",\n'
                '            "GroupConcat",\n'
                '            "Pow",\n'
                '            "RegexpLike",\n'
                '            "DPipe",\n'
                '            "Dot",\n'
                "        )\n"
                "        if cls.__name__ in extra_refuse:\n"
                '            return _refuse("FUNCTION_NOT_ALLOWED", cls.__name__)\n',
                "        if isinstance(child, exp.Anonymous):\n"
                '            return _refuse("FUNCTION_NOT_ALLOWED", child.name or cls.__name__)\n'
                "        refuse_types = (\n"
                "            exp.Window,\n"
                "            exp.Filter,\n"
                "            exp.Lateral,\n"
                "            exp.Values,\n"
                "            exp.TableSample,\n"
                "            exp.Fetch,\n"
                "            exp.RawString,\n"
                "            exp.UnicodeString,\n"
                "            exp.ByteString,\n"
                "        )\n"
                "        for rt in refuse_types:\n"
                "            if isinstance(child, rt):\n"
                '                return _refuse("UNSUPPORTED_SYNTAX", cls.__name__)\n'
                "        extra_refuse = (\n"
                '            "CurrentVersion",\n'
                '            "Explode",\n'
                '            "ExplodingGenerateSeries",\n'
                '            "Rand",\n'
                '            "Repeat",\n'
                '            "Pad",\n'
                '            "GroupConcat",\n'
                '            "RegexpLike",\n'
                '            "DPipe",\n'
                '            "Dot",\n'
                "        )\n"
                "        if cls.__name__ in extra_refuse:\n"
                '            return _refuse("FUNCTION_NOT_ALLOWED", cls.__name__)\n',
            ),
        ),
        "tests/test_mutant_targets.py::test_m12_pow",
    ),
]

FAIL_RE = re.compile(r"^FAILED (?P<nodeid>\S+) - (?P<err>\S+)")


def _apply_patches(tree: Path, patches: tuple[Patch, ...]) -> None:
    for patch in patches:
        target = tree / patch.path
        text = target.read_text(encoding="utf-8")
        count = text.count(patch.search)
        if count != 1:
            raise SystemExit(f"search matched {count} times in {patch.path}, expected 1")
        target.write_text(text.replace(patch.search, patch.replace, 1), encoding="utf-8")


def _run_targets(tree: Path) -> tuple[int, dict[str, str]]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "tests/test_mutant_targets.py",
            "-rf",
            "--tb=line",
        ],
        cwd=tree,
        env={**os.environ, "PYTHONPATH": str(tree / "src")},
        capture_output=True,
        text=True,
        timeout=120,
    )
    failures: dict[str, str] = {}
    for line in proc.stdout.splitlines() + proc.stderr.splitlines():
        match = FAIL_RE.match(line)
        if match:
            failures[match.group("nodeid")] = match.group("err")
    return proc.returncode, failures


def main() -> None:
    baseline = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "tests/test_mutant_targets.py",
            "-q",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    if baseline.returncode != 0:
        raise SystemExit("baseline mutant targets not green")

    print("mutant_id | killed | target")
    killed = 0
    for mutant in MUTANTS:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "repo"
            shutil.copytree(ROOT, tree, dirs_exist_ok=False)
            _apply_patches(tree, mutant.patches)
            code, failed = _run_targets(tree)
            if code != 1:
                raise SystemExit(f"{mutant.mutant_id} kill failed: exit={code} failed={failed}")
            if set(failed) != {mutant.target_test}:
                raise SystemExit(
                    f"{mutant.mutant_id} kill failed: exit={code} failed={set(failed)}"
                )
            for nodeid, err in failed.items():
                allowed = err.startswith(("AssertionError", "assert"))
                if not allowed:
                    raise SystemExit(f"{mutant.mutant_id} kill failed: {nodeid} raised {err}")
            print(f"{mutant.mutant_id} | yes | {mutant.target_test}")
            killed += 1
    print(f"killed {killed}/{len(MUTANTS)}")


if __name__ == "__main__":
    main()
