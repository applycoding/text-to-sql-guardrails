# SPDX-License-Identifier: Apache-2.0
"""Apply one source patch at a time and run mutant target tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Mutant:
    mutant_id: str
    path: str
    search: str
    replace: str
    target_test: str


MUTANTS: list[Mutant] = [
    Mutant(
        "M1",
        "src/t2sql/guard.py",
        '    if cfg.single_statement and len(statements) > 1:\n        return _refuse("MULTI_STATEMENT", str(len(statements)))\n',
        "",
        "tests/test_mutant_targets.py::test_m1_stacked",
    ),
    Mutant(
        "M2",
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
        "tests/test_mutant_targets.py::test_m2_do_block",
    ),
    Mutant(
        "M3",
        "src/t2sql/guard.py",
        '    shadow = cte_names & policy.ALLOWED_TABLES\n    if shadow:\n        return _refuse("CTE_SHADOWS_TABLE", f"CTE shadows table: {sorted(shadow)[0]}")\n',
        "",
        "tests/test_mutant_targets.py::test_m3_cte_shadow",
    ),
    Mutant(
        "M4",
        "src/t2sql/guard.py",
        '            if schema_part:\n                schema_ok = not schema_quoted and schema_part.lower() == policy.ALLOWED_SCHEMA\n                if not schema_ok:\n                    return _refuse("TABLE_NOT_ALLOWED", f"{schema_part}.{name}")\n',
        "",
        "tests/test_mutant_targets.py::test_m4_public_orders",
    ),
    Mutant(
        "M5",
        "src/t2sql/guard.py",
        "        if isinstance(child, exp.Table):\n"
        "            if isinstance(child.this, (exp.Anonymous, exp.ExplodingGenerateSeries)):\n"
        '                return _refuse("FUNCTION_NOT_ALLOWED", "function relation")\n',
        "        if isinstance(child, exp.Table):\n            pass\n",
        "tests/test_mutant_targets.py::test_m5_dblink_from",
    ),
    Mutant(
        "M6",
        "src/t2sql/policy.py",
        '    "customers": frozenset({"id", "name", "city", "signup_date"}),\n',
        '    "customers": frozenset({"id", "name", "city", "signup_date", "email"}),\n',
        "tests/test_mutant_targets.py::test_m6_email",
    ),
    Mutant(
        "M7",
        "src/t2sql/guard.py",
        "            if val > policy.MAX_LIMIT:\n"
        '                sel.set("limit", exp.Limit(expression=exp.Literal.number(policy.MAX_LIMIT)))\n',
        "",
        "tests/test_mutant_targets.py::test_m7_limit_clamp",
    ),
    Mutant(
        "M8",
        "src/t2sql/guard.py",
        "    whole = _whole_row_refs(node)\n    if whole:\n        return whole\n",
        "",
        "tests/test_mutant_targets.py::test_m8_whole_row",
    ),
    Mutant(
        "M9",
        "src/t2sql/explain.py",
        '    for node in _walk_plans(root):\n        if "Plan Rows" in node:\n            max_rows = max(max_rows, float(node["Plan Rows"]))\n',
        '    if "Plan Rows" in root:\n        max_rows = float(root["Plan Rows"])\n',
        "tests/test_mutant_targets.py::test_m9_dryrun_rows",
    ),
    Mutant(
        "M10",
        "src/t2sql/explain.py",
        '    if summary.total_cost > policy.MAX_PLAN_COST:\n        return False, "DRYRUN_COST"\n',
        "",
        "tests/test_mutant_targets.py::test_m10_synthetic_cost",
    ),
    Mutant(
        "M11",
        "src/t2sql/guard.py",
        '        if isinstance(child, exp.Cast):\n            if child.to and not _is_allowed_cast(child.to):\n                return _refuse("CAST_NOT_ALLOWED", child.to.sql())\n',
        "",
        "tests/test_mutant_targets.py::test_m11_regclass_cast",
    ),
    Mutant(
        "M12",
        "src/t2sql/guard.py",
        '        if isinstance(child, (exp.Binary, exp.Unary)) and cls not in policy.STRUCTURAL_NODES:\n            return _refuse("FUNCTION_NOT_ALLOWED", cls.__name__)\n',
        "",
        "tests/test_mutant_targets.py::test_m12_pow",
    ),
]


def _apply_patch(tree: Path, mutant: Mutant) -> None:
    target = tree / mutant.path
    text = target.read_text(encoding="utf-8")
    count = text.count(mutant.search)
    if count != 1:
        raise SystemExit(f"{mutant.mutant_id}: search matched {count} times, expected 1")
    target.write_text(text.replace(mutant.search, mutant.replace, 1), encoding="utf-8")


def _run_targets(tree: Path) -> tuple[int, set[str]]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "tests/test_mutant_targets.py",
            "-q",
        ],
        cwd=tree,
        env={**os.environ, "PYTHONPATH": str(tree / "src")},
        capture_output=True,
        text=True,
        timeout=120,
    )
    failed: set[str] = set()
    for line in proc.stdout.splitlines() + proc.stderr.splitlines():
        if line.startswith("FAILED "):
            part = line.split()[1]
            failed.add(part)
    return proc.returncode, failed


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
            _apply_patch(tree, mutant)
            code, failed = _run_targets(tree)
            ok = code != 0 and failed == {mutant.target_test}
            if not ok:
                raise SystemExit(f"{mutant.mutant_id} kill failed: exit={code} failed={failed}")
            print(f"{mutant.mutant_id} | yes | {mutant.target_test}")
            killed += 1
    print(f"killed {killed}/{len(MUTANTS)}")


if __name__ == "__main__":
    main()
