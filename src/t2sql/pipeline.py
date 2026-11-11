# SPDX-License-Identifier: Apache-2.0
"""Model -> guard -> executor pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from t2sql import executor
from t2sql.guard import GuardConfig, check
from t2sql.model import Model


@dataclass(frozen=True)
class PipelineResult:
    code: str
    detail: str
    sql: str | None
    rows: list[list[Any]] | None


def run_question(model: Model, question: str, cfg: GuardConfig | None = None) -> PipelineResult:
    if cfg is None:
        cfg = GuardConfig()
    sql = model.to_sql(question)
    if sql is None:
        return PipelineResult("NO_TEMPLATE", "no template", None, None)
    return run_sql(sql, cfg)


def run_sql(sql: str, cfg: GuardConfig | None = None) -> PipelineResult:
    if cfg is None:
        cfg = GuardConfig()
    verdict = check(sql, cfg)
    if not verdict.ok:
        return PipelineResult(verdict.code, verdict.detail, verdict.sql, None)
    exec_result = executor.run(verdict.sql or sql, cfg)
    return PipelineResult(
        exec_result.code,
        exec_result.detail,
        exec_result.sql,
        exec_result.rows,
    )
