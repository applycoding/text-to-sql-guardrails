# SPDX-License-Identifier: Apache-2.0
"""Parser-based SQL guard (pure Python, no database import)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

import sqlglot
from sqlglot import exp
from sqlglot.optimizer import qualify

from t2sql import policy

QUOTE_FUNC_RE = re.compile(r'"[^"]+"\s*\(', re.IGNORECASE)


@dataclass(frozen=True)
class Verdict:
    ok: bool
    code: str
    detail: str
    sql: str | None


@dataclass(frozen=True)
class GuardConfig:
    single_statement: bool = True
    statement_type: bool = True
    tables: bool = True
    nodes: bool = True
    columns: bool = True
    limit: bool = True
    dry_run: bool = True


def _refuse(code: str, detail: str = "") -> Verdict:
    return Verdict(ok=False, code=code, detail=detail or code, sql=None)


def _accept(sql: str) -> Verdict:
    return Verdict(ok=True, code="OK", detail="", sql=sql)


def _count_nodes(node: exp.Expression) -> int:
    return sum(1 for _ in node.walk())


def _statements(raw: str) -> list[exp.Expression]:
    return [cast(exp.Expression, stmt) for stmt in sqlglot.parse(raw, read="postgres") if stmt]


def _strip_comment_only_tail(stmts: list[exp.Expression], raw: str) -> list[exp.Expression]:
    """Return statements after removing a trailing comment-only fragment if any."""
    if len(stmts) <= 1:
        return stmts
    return stmts


def _forbidden_nodes(node: exp.Expression) -> exp.Expression | None:
    for child in node.walk():
        for forbidden in policy.FORBIDDEN_STATEMENT_NODES:
            if isinstance(child, forbidden):
                return cast(exp.Expression, child)
    return None


def _has_select_into(node: exp.Expression) -> bool:
    for child in node.walk():
        if isinstance(child, exp.Select) and child.args.get("into") is not None:
            return True
    return False


def _has_locking(node: exp.Expression) -> bool:
    for child in node.walk():
        if isinstance(child, exp.Select) and child.args.get("locks"):
            return True
    return False


def _has_recursive_cte(node: exp.Expression) -> bool:
    with_clause = node.find(exp.With)
    if with_clause is None:
        return False
    if with_clause.args.get("recursive"):
        return True
    for cte in with_clause.expressions:
        if cte.args.get("recursive"):
            return True
    return False


def _cte_names(node: exp.Expression) -> set[str]:
    names: set[str] = set()
    with_clause = node.find(exp.With)
    if with_clause:
        for cte in with_clause.expressions:
            alias = cte.alias
            if alias:
                if isinstance(alias, str):
                    names.add(alias.lower())
                elif alias.this:
                    names.add(alias.this.name.lower())
    return names


def _table_name(table: exp.Table) -> tuple[str | None, str, bool, bool]:
    catalog = table.catalog or None
    db = table.db or None
    name = table.name
    ident = table.this
    table_quoted = isinstance(ident, exp.Identifier) and ident.quoted
    db_node = table.args.get("db")
    schema_quoted = isinstance(db_node, exp.Identifier) and db_node.quoted
    if catalog:
        return catalog, name, table_quoted, schema_quoted
    if db:
        return db, name, table_quoted, schema_quoted
    return None, name, table_quoted, schema_quoted


def _check_tables(node: exp.Expression) -> Verdict | None:
    cte_names = _cte_names(node)
    shadow = cte_names & policy.ALLOWED_TABLES
    if shadow:
        return _refuse("CTE_SHADOWS_TABLE", f"CTE shadows table: {sorted(shadow)[0]}")

    for child in node.walk():
        if isinstance(child, exp.From):
            source = child.this
            if isinstance(source, exp.Table) and isinstance(
                source.this, exp.ExplodingGenerateSeries
            ):
                return _refuse("FUNCTION_NOT_ALLOWED", "generate_series")
        if isinstance(child, exp.Table):
            if isinstance(child.this, (exp.Anonymous, exp.ExplodingGenerateSeries)):
                return _refuse("FUNCTION_NOT_ALLOWED", "function relation")
            schema_part, name, table_quoted, schema_quoted = _table_name(child)
            lname = name.lower() if name and not table_quoted else name
            if schema_part and schema_part.lower() in (
                "pg_catalog",
                "information_schema",
            ):
                return _refuse("SYSTEM_CATALOG", schema_part)
            if lname and lname.startswith("pg_"):
                return _refuse("SYSTEM_CATALOG", lname)
            if schema_part:
                schema_ok = not schema_quoted and schema_part.lower() == policy.ALLOWED_SCHEMA
                if not schema_ok:
                    return _refuse("TABLE_NOT_ALLOWED", f"{schema_part}.{name}")
            table_ok = (not table_quoted and lname in policy.ALLOWED_TABLES) or (
                table_quoted and name in policy.ALLOWED_TABLES
            )
            if not table_ok and lname not in cte_names and name not in cte_names:
                return _refuse("TABLE_NOT_ALLOWED", name or lname)
        if isinstance(child, exp.From):
            for table_expr in child.expressions:
                if isinstance(table_expr, exp.Anonymous):
                    return _refuse("FUNCTION_NOT_ALLOWED", str(table_expr))
    return None


def _is_allowed_cast(dtype: exp.DataType) -> bool:
    base = dtype.this
    if isinstance(base, exp.DataType.Type):
        name = base.value
    else:
        name = str(base).lower()
    if name not in policy.ALLOWED_CAST_TYPES:
        return False
    if name == "numeric" and (dtype.expressions or (isinstance(base, str) and "(" in base)):
        return False
    return True


def _node_class_allowed(cls: type) -> bool:
    if cls in policy.STRUCTURAL_NODES or cls in policy.FUNCTION_NODES:
        return True
    if issubclass(cls, (exp.Binary, exp.Unary)) and cls in policy.STRUCTURAL_NODES:
        return True
    if cls in (
        exp.Expression,
        exp.Condition,
        exp.Predicate,
        exp.Func,
        exp.DataType,
        exp.UserDefinedFunction,
    ):
        return True
    return False


def _check_nodes(node: exp.Expression) -> Verdict | None:
    for child in node.walk():
        cls = type(child)
        if isinstance(child, exp.Cast):
            if child.to and not _is_allowed_cast(child.to):
                return _refuse("CAST_NOT_ALLOWED", child.to.sql())
        if isinstance(child, exp.DataType):
            parent = child.parent
            if parent and isinstance(parent, exp.Cast):
                if not _is_allowed_cast(child):
                    return _refuse("CAST_NOT_ALLOWED", child.sql())
            continue
        if isinstance(child, (exp.Binary, exp.Unary)) and cls not in policy.STRUCTURAL_NODES:
            return _refuse("FUNCTION_NOT_ALLOWED", cls.__name__)
        if isinstance(child, exp.Anonymous):
            return _refuse("FUNCTION_NOT_ALLOWED", child.name or cls.__name__)
        refuse_types = (
            exp.Window,
            exp.Filter,
            exp.Lateral,
            exp.Values,
            exp.TableSample,
            exp.Fetch,
            exp.RawString,
            exp.UnicodeString,
            exp.ByteString,
        )
        for rt in refuse_types:
            if isinstance(child, rt):
                return _refuse("UNSUPPORTED_SYNTAX", cls.__name__)
        extra_refuse = (
            "CurrentVersion",
            "Explode",
            "ExplodingGenerateSeries",
            "Rand",
            "Repeat",
            "Pad",
            "GroupConcat",
            "Pow",
            "RegexpLike",
            "DPipe",
            "Dot",
        )
        if cls.__name__ in extra_refuse:
            return _refuse("FUNCTION_NOT_ALLOWED", cls.__name__)
        if not _node_class_allowed(cls):
            return _refuse("UNSUPPORTED_SYNTAX", cls.__name__)
    return None


def _whole_row_refs(node: exp.Expression) -> Verdict | None:
    aliases: set[str] = set()
    for ta in node.find_all(exp.TableAlias):
        if ta.this and isinstance(ta.this, exp.Identifier):
            aliases.add(ta.this.name.lower())
    for col in node.find_all(exp.Column):
        name = (col.name or "").lower()
        if name and name in aliases and not col.table:
            return _refuse("WHOLE_ROW_REFERENCE", col.name)
    return None


def _qualify_schema() -> dict[str, dict[str, str]]:
    schema: dict[str, dict[str, str]] = {}
    for table, cols in policy.ALLOWED_COLUMNS.items():
        schema[table] = {col: "text" for col in cols}
    return schema


def _cte_column_schema(node: exp.Expression) -> dict[str, dict[str, str]]:
    schema = _qualify_schema()
    with_clause = node.find(exp.With)
    if not with_clause:
        return schema
    for cte in with_clause.expressions:
        alias = cte.alias
        cte_name: str | None = None
        if isinstance(alias, str):
            cte_name = alias.lower()
        elif alias and alias.this:
            cte_name = alias.this.name.lower()
        if not cte_name:
            continue
        cols: list[str] = []
        body = cte.this
        if isinstance(body, exp.Select):
            for expr in body.expressions:
                if isinstance(expr, exp.Alias):
                    cols.append(expr.alias)
                elif isinstance(expr, exp.Column):
                    cols.append(expr.name)
                elif isinstance(expr, exp.Star):
                    cols.extend(["*"])
        schema[cte_name] = {col: "text" for col in cols} if cols else {"*": "text"}
    return schema


def _check_columns(node: exp.Expression) -> Verdict | None:
    whole = _whole_row_refs(node)
    if whole:
        return whole
    try:
        qualified = qualify.qualify(
            node.copy(),
            schema=cast(dict[str, object], _cte_column_schema(node)),
            dialect="postgres",
            expand_stars=True,
            validate_qualify_columns=True,
        )
    except Exception as exc:
        return _refuse("COLUMN_NOT_ALLOWED", str(exc))
    _ = qualified
    return None


def _apply_limit(node: exp.Expression) -> exp.Expression:
    out = node.copy()

    def clamp_select(sel: exp.Select) -> None:
        lim = sel.args.get("limit")
        if lim is None:
            sel.set("limit", exp.Limit(expression=exp.Literal.number(policy.MAX_LIMIT)))
            return
        expr = lim.expression
        if isinstance(expr, exp.Literal) and expr.is_number:
            val = int(expr.this)
            if val > policy.MAX_LIMIT:
                sel.set("limit", exp.Limit(expression=exp.Literal.number(policy.MAX_LIMIT)))

    if isinstance(out, exp.Select):
        clamp_select(out)
    elif isinstance(out, (exp.Union, exp.Intersect, exp.Except)):
        wrapped = exp.Select(
            expressions=[exp.Star()],
            from_=exp.From(
                this=exp.Subquery(this=out, alias=exp.TableAlias(this=exp.Identifier(this="q")))
            ),
            limit=exp.Limit(expression=exp.Literal.number(policy.MAX_LIMIT)),
        )
        return wrapped
    return out


def _check_limit(node: exp.Expression, cfg: GuardConfig) -> tuple[Verdict | None, exp.Expression]:
    out = node.copy()
    for sel in out.find_all(exp.Select):
        lim = sel.args.get("limit")
        if lim is not None:
            expr = lim.expression
            if expr is None or not (isinstance(expr, exp.Literal) and expr.is_number):
                return _refuse("LIMIT_NOT_LITERAL", "limit"), out
        off = sel.args.get("offset")
        if off is not None:
            off_expr = off.expression if hasattr(off, "expression") else off.this
            if not (isinstance(off_expr, exp.Literal) and off_expr.is_number):
                return _refuse("OFFSET_NOT_ALLOWED", "offset"), out
            off_val = int(off_expr.this)
            if off_val > policy.MAX_OFFSET:
                return _refuse("OFFSET_NOT_ALLOWED", str(off_val)), out
    if cfg.limit:
        out = _apply_limit(out)
    return None, out


def check(sql: str, cfg: GuardConfig | None = None) -> Verdict:
    if cfg is None:
        cfg = GuardConfig()

    if len(sql) > policy.MAX_SQL_LENGTH:
        return _refuse("TOO_LONG", str(len(sql)))

    stripped = sql.strip()
    if not stripped:
        return _refuse("EMPTY", "empty input")

    if QUOTE_FUNC_RE.search(sql):
        return _refuse("QUOTED_FUNCTION", "quoted identifier before (")

    try:
        statements = _statements(sql)
    except sqlglot.errors.ParseError as exc:
        return _refuse("PARSE_ERROR", str(exc))

    if not statements:
        return _refuse("EMPTY", "no statements")

    if cfg.single_statement and len(statements) > 1:
        return _refuse("MULTI_STATEMENT", str(len(statements)))

    tree = statements[0]
    try:
        tree = sqlglot.optimizer.normalize_identifiers.normalize_identifiers(
            tree, dialect="postgres"
        )
    except sqlglot.errors.ParseError as exc:
        return _refuse("PARSE_ERROR", str(exc))
    except RecursionError:
        return _refuse("TOO_COMPLEX", "recursion")

    try:
        node_count = _count_nodes(tree)
    except RecursionError:
        return _refuse("TOO_COMPLEX", "recursion")

    if node_count > policy.MAX_AST_NODES:
        return _refuse("TOO_COMPLEX", str(node_count))

    if cfg.statement_type:
        if type(tree) not in policy.ALLOWED_ROOT_TYPES:
            return _refuse("STATEMENT_NOT_ALLOWED", type(tree).__name__)
        forb = _forbidden_nodes(tree)
        if forb is not None:
            return _refuse("STATEMENT_NOT_ALLOWED", type(forb).__name__)
        if _has_select_into(tree):
            return _refuse("SELECT_INTO", "INTO")
        if _has_locking(tree):
            return _refuse("LOCKING_CLAUSE", "locking")
        if _has_recursive_cte(tree):
            return _refuse("RECURSIVE_CTE", "recursive")

    if cfg.tables:
        verdict = _check_tables(tree)
        if verdict:
            return verdict

    if cfg.nodes:
        verdict = _check_nodes(tree)
        if verdict:
            return verdict

    limit_verdict, tree = _check_limit(tree, cfg)
    if limit_verdict:
        return limit_verdict

    if cfg.columns:
        verdict = _check_columns(tree)
        if verdict:
            return verdict

    try:
        tree = qualify.qualify(
            tree,
            schema=cast(dict[str, object], _cte_column_schema(tree)),
            dialect="postgres",
            expand_stars=True,
            validate_qualify_columns=False,
        )
    except Exception:
        pass

    emitted = tree.sql(dialect="postgres", comments=False)
    try:
        reparsed = sqlglot.parse_one(emitted, read="postgres")
        re_emitted = reparsed.sql(dialect="postgres", comments=False)
    except sqlglot.errors.ParseError:
        return _refuse("REEMIT_MISMATCH", "reparse failed")

    if re_emitted != emitted:
        return _refuse("REEMIT_MISMATCH", "mismatch")

    return _accept(emitted)
