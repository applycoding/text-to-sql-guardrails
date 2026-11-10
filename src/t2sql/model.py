# SPDX-License-Identifier: Apache-2.0
"""Model interface and deterministic stub."""

from __future__ import annotations

import os
import re
from typing import Protocol

import sqlglot
from sqlglot import exp

from t2sql.policy import ORDER_STATUSES, SEEDED_CITIES

STRICT_MONTH_RE = re.compile(
    r"^orders per month in (20\d{2})$",
    re.IGNORECASE,
)
CITY_RE = re.compile(r"^how many customers (?:are )?in ([a-z]+)\??$", re.IGNORECASE)
STATUS_RE = re.compile(
    r"^how many orders (?:are|were) ([a-z]+)\??$",
    re.IGNORECASE,
)
TOP_RE = re.compile(r"^top (\d{1,2}) products by revenue\??$", re.IGNORECASE)
CATEGORY_RE = re.compile(r"^revenue by category\??$", re.IGNORECASE)


class Model(Protocol):
    def to_sql(self, question: str) -> str | None: ...


def _normalize_question(question: str) -> str:
    text = question.strip().lower()
    text = re.sub(r"\s+", " ", text)
    if text.endswith("?"):
        text = text[:-1].strip()
    return text


class StubModel:
    def to_sql(self, question: str) -> str | None:
        q = _normalize_question(question)
        if not q:
            return None

        m = CITY_RE.match(q)
        if m:
            city = m.group(1).lower()
            if city not in SEEDED_CITIES:
                return None
            city_lit = exp.Literal.string(
                {
                    "denver": "Denver",
                    "boulder": "Boulder",
                    "austin": "Austin",
                    "seattle": "Seattle",
                    "portland": "Portland",
                    "chicago": "Chicago",
                    "boston": "Boston",
                    "miami": "Miami",
                }[city]
            )
            sel = exp.select(exp.Count(this=exp.Star())).from_("customers")
            sel = sel.where(exp.Column(this="city").eq(city_lit))
            return sel.sql(dialect="postgres")

        m = STATUS_RE.match(q)
        if m:
            status = m.group(1).lower()
            if status not in ORDER_STATUSES:
                return None
            status_lit = exp.Literal.string(status)
            sel = exp.select(exp.Count(this=exp.Star())).from_("orders")
            sel = sel.where(exp.Column(this="status").eq(status_lit))
            return sel.sql(dialect="postgres")

        m = TOP_RE.match(q)
        if m:
            n = int(m.group(1))
            if n > 99:
                return None
            top_sql = sqlglot.parse_one(
                (
                    "SELECT p.name, SUM(oi.quantity * oi.unit_price_cents) AS revenue_cents "
                    "FROM products p "
                    "JOIN order_items oi ON oi.product_id = p.id "
                    "GROUP BY p.id, p.name "
                    f"ORDER BY revenue_cents DESC, p.id LIMIT {n}"
                ),
                read="postgres",
            ).sql(dialect="postgres")
            return top_sql

        if CATEGORY_RE.match(q):
            return sqlglot.parse_one(
                (
                    "SELECT p.category, SUM(oi.quantity * oi.unit_price_cents) AS revenue_cents "
                    "FROM products p "
                    "JOIN order_items oi ON oi.product_id = p.id "
                    "GROUP BY p.category "
                    "ORDER BY p.category"
                ),
                read="postgres",
            ).sql(dialect="postgres")

        m = STRICT_MONTH_RE.match(q)
        if m:
            year = int(m.group(1))
            month_query = sqlglot.parse_one(
                (
                    "SELECT date_trunc('month', ordered_at)::date AS month, "
                    "COUNT(*) AS order_count "
                    "FROM orders "
                    f"WHERE ordered_at >= '{year}-01-01' AND ordered_at < '{year + 1}-01-01' "
                    "GROUP BY month ORDER BY month"
                ),
                read="postgres",
            )
            return month_query.sql(dialect="postgres")

        if "atlantis" in q or "pg_sleep" in q or "staff" in q or "drop table" in q:
            return None
        if "top 1000" in q or "ignore previous" in q:
            return None
        return None


def make_model() -> Model:
    kind = os.environ.get("T2SQL_MODEL", "stub")
    if kind in ("", "stub"):
        return StubModel()
    if kind == "openai-compatible":
        from t2sql.adapters.openai_compat import OpenAICompatModel

        return OpenAICompatModel()
    raise SystemExit(2)
