# SPDX-License-Identifier: Apache-2.0
"""EXPLAIN plan JSON evaluation (pure)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from t2sql import policy


@dataclass(frozen=True)
class ExplainSummary:
    total_cost: float
    max_plan_rows: float


def _walk_plans(plan: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [plan]
    for child in plan.get("Plans", []) or []:
        out.extend(_walk_plans(child))
    for key in ("Init Plan", "Subplans"):
        sub = plan.get(key)
        if sub:
            for item in sub:
                if isinstance(item, dict) and "Plan" in item:
                    out.extend(_walk_plans(item["Plan"]))
                elif isinstance(item, dict):
                    out.extend(_walk_plans(item))
    return out


def evaluate(plan_json: list[dict[str, Any]]) -> ExplainSummary:
    if not plan_json or not isinstance(plan_json[0], dict):
        raise ValueError("malformed plan")
    root = plan_json[0].get("Plan")
    if not isinstance(root, dict):
        raise ValueError("missing Plan")
    if "Total Cost" not in root:
        raise ValueError("missing Total Cost")
    total_cost = float(root["Total Cost"])
    max_rows = 0.0
    for node in _walk_plans(root):
        if "Plan Rows" in node:
            max_rows = max(max_rows, float(node["Plan Rows"]))
    return ExplainSummary(total_cost=total_cost, max_plan_rows=max_rows)


def dry_run_verdict(summary: ExplainSummary) -> tuple[bool, str]:
    if summary.total_cost > policy.MAX_PLAN_COST:
        return False, "DRYRUN_COST"
    if summary.max_plan_rows > policy.MAX_PLAN_ROWS:
        return False, "DRYRUN_ROWS"
    return True, "OK"
