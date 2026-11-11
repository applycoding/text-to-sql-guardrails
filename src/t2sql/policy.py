# SPDX-License-Identifier: Apache-2.0
"""Allow-lists, bounds and reason codes (constants only)."""

from __future__ import annotations

from sqlglot import exp

MAX_SQL_LENGTH = 4000
MAX_AST_NODES = 400
MAX_LIMIT = 100
MAX_OFFSET = 1000
MAX_PLAN_COST = 50_000
MAX_PLAN_ROWS = 1_000_000
STATEMENT_TIMEOUT_MS = 2000
MAX_RESULT_BYTES = 1_048_576

ALLOWED_TABLES: frozenset[str] = frozenset({"customers", "products", "orders", "order_items"})

ALLOWED_SCHEMA = "shop"

ALLOWED_COLUMNS: dict[str, frozenset[str]] = {
    "customers": frozenset({"id", "name", "city", "signup_date"}),
    "products": frozenset({"id", "name", "category", "price_cents"}),
    "orders": frozenset({"id", "customer_id", "ordered_at", "status"}),
    "order_items": frozenset({"order_id", "product_id", "quantity", "unit_price_cents"}),
}

STRUCTURAL_NODES: frozenset[type] = frozenset(
    {
        exp.Select,
        exp.Union,
        exp.Intersect,
        exp.Except,
        exp.From,
        exp.Join,
        exp.Table,
        exp.TableAlias,
        exp.Identifier,
        exp.Column,
        exp.Star,
        exp.Alias,
        exp.Literal,
        exp.Boolean,
        exp.Null,
        exp.Where,
        exp.Group,
        exp.Having,
        exp.Order,
        exp.Ordered,
        exp.Limit,
        exp.Offset,
        exp.Subquery,
        exp.With,
        exp.CTE,
        exp.Paren,
        exp.Neg,
        exp.Not,
        exp.And,
        exp.Or,
        exp.EQ,
        exp.NEQ,
        exp.GT,
        exp.GTE,
        exp.LT,
        exp.LTE,
        exp.Is,
        exp.In,
        exp.Between,
        exp.Like,
        exp.ILike,
        exp.Add,
        exp.Sub,
        exp.Mul,
        exp.Div,
        exp.Mod,
        exp.Exists,
        exp.DataType,
        exp.Var,
        exp.Distinct,
        exp.Case,
        exp.If,
        exp.Tuple,
    }
)

FUNCTION_NODES: frozenset[type] = frozenset(
    {
        exp.Count,
        exp.Sum,
        exp.Avg,
        exp.Min,
        exp.Max,
        exp.Round,
        exp.Coalesce,
        exp.Lower,
        exp.Upper,
        exp.Abs,
        exp.Length,
        exp.Cast,
        exp.Extract,
        exp.TimestampTrunc,
        exp.DateTrunc,
        exp.CurrentDate,
        exp.Nullif,
    }
)

ALLOWED_CAST_TYPES: frozenset[str] = frozenset(
    {"int", "bigint", "smallint", "text", "date", "numeric"}
)

FORBIDDEN_STATEMENT_NODES: frozenset[type] = frozenset(
    {
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Merge,
        exp.Create,
        exp.Drop,
        exp.Alter,
        exp.Copy,
        exp.Set,
        exp.Transaction,
        exp.Commit,
        exp.Rollback,
        exp.Command,
    }
)

ALLOWED_ROOT_TYPES: frozenset[type] = frozenset({exp.Select, exp.Union, exp.Intersect, exp.Except})

SEEDED_CITIES: frozenset[str] = frozenset(
    {"denver", "boulder", "austin", "seattle", "portland", "chicago", "boston", "miami"}
)

ORDER_STATUSES: frozenset[str] = frozenset({"placed", "shipped", "delivered", "returned"})
