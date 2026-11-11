# SPDX-License-Identifier: Apache-2.0
"""PLAN section 9 attack suite."""

from __future__ import annotations

import pytest

from t2sql.guard import check

ATTACKS: list[tuple[str, str, str, str | None]] = [
    ("stacked", "SELECT 1; DROP TABLE shop.orders", "MULTI_STATEMENT", None),
    (
        "comment_split",
        "SELECT * FROM orders /* */; DELETE FROM orders",
        "MULTI_STATEMENT",
        None,
    ),
    (
        "comment_tail",
        "SELECT * FROM orders -- ; DROP TABLE x",
        "OK",
        'SELECT "orders"."customer_id" AS "customer_id", "orders"."id" AS "id", "orders"."ordered_at" AS "ordered_at", "orders"."status" AS "status" FROM "shop"."orders" AS "orders" LIMIT 100',
    ),
    (
        "nested_comment",
        "SELECT 1 /* nested /* c */ ; DROP */",
        "OK",
        'SELECT 1 AS "1" LIMIT 100',
    ),
    (
        "string_semicolon",
        "SELECT 'a;b' AS s; ",
        "OK",
        'SELECT \'a;b\' AS "s" LIMIT 100',
    ),
    ("dollar_quote", "SELECT $q$; DROP TABLE x$q$", "UNSUPPORTED_SYNTAX", None),
    (
        "cte_no_limit",
        "WITH a AS (SELECT id FROM orders) SELECT * FROM a",
        "OK",
        'WITH "a" AS (SELECT "orders"."id" AS "id" FROM "shop"."orders" AS "orders") SELECT "a"."id" AS "id" FROM "a" AS "a" LIMIT 100',
    ),
    (
        "tautology",
        "SELECT * FROM customers WHERE name = '' OR 1=1 --'",
        "OK",
        'SELECT "customers"."city" AS "city", "customers"."id" AS "id", "customers"."name" AS "name", "customers"."signup_date" AS "signup_date" FROM "shop"."customers" AS "customers" WHERE "customers"."name" = \'\' OR 1 = 1 LIMIT 100',
    ),
    (
        "insert",
        "INSERT INTO orders VALUES (1, 1, '2025-01-01', 'x')",
        "STATEMENT_NOT_ALLOWED",
        None,
    ),
    (
        "update",
        "UPDATE orders SET status = 'x'",
        "STATEMENT_NOT_ALLOWED",
        None,
    ),
    (
        "copy",
        "COPY orders TO '/tmp/x'",
        "STATEMENT_NOT_ALLOWED",
        None,
    ),
    (
        "set",
        "SET statement_timeout = 0",
        "STATEMENT_NOT_ALLOWED",
        None,
    ),
    (
        "dml_cte",
        "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x",
        "STATEMENT_NOT_ALLOWED",
        None,
    ),
    (
        "explain_analyze",
        "EXPLAIN ANALYZE SELECT * FROM orders",
        "STATEMENT_NOT_ALLOWED",
        None,
    ),
    (
        "do_block",
        "DO $$ BEGIN PERFORM pg_sleep(1); END $$",
        "STATEMENT_NOT_ALLOWED",
        None,
    ),
    ("select_into", "SELECT * INTO newt FROM orders", "SELECT_INTO", None),
    ("for_update", "SELECT * FROM orders FOR UPDATE", "LOCKING_CLAUSE", None),
    (
        "recursive_cte",
        "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r) SELECT sum(n) FROM r",
        "RECURSIVE_CTE",
        None,
    ),
    (
        "cte_shadow",
        "WITH customers AS (SELECT * FROM staff_salaries) SELECT * FROM customers",
        "CTE_SHADOWS_TABLE",
        None,
    ),
    ("pg_user", "SELECT * FROM pg_catalog.pg_user", "SYSTEM_CATALOG", None),
    (
        "info_schema",
        "SELECT * FROM information_schema.tables",
        "SYSTEM_CATALOG",
        None,
    ),
    (
        "pg_stat",
        "SELECT * FROM (SELECT * FROM pg_stat_activity) s",
        "SYSTEM_CATALOG",
        None,
    ),
    ("staff_salaries", "SELECT * FROM staff_salaries", "TABLE_NOT_ALLOWED", None),
    (
        "public_staff",
        "SELECT * FROM public.staff_salaries",
        "TABLE_NOT_ALLOWED",
        None,
    ),
    (
        "wrong_schema",
        "SELECT * FROM shopdemo.shop.orders",
        "TABLE_NOT_ALLOWED",
        None,
    ),
    ('"Customers"', 'SELECT * FROM "Customers"', "TABLE_NOT_ALLOWED", None),
    (
        "wrong_shop_case",
        'SELECT * FROM "SHOP"."customers"',
        "TABLE_NOT_ALLOWED",
        None,
    ),
    (
        "union_staff",
        "SELECT id FROM orders UNION SELECT staff_id FROM staff_salaries",
        "TABLE_NOT_ALLOWED",
        None,
    ),
    (
        "scalar_staff",
        "SELECT (SELECT salary_cents FROM staff_salaries LIMIT 1)",
        "TABLE_NOT_ALLOWED",
        None,
    ),
    (
        "pg_read_file",
        "SELECT pg_read_file('/etc/passwd')",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    ("pg_sleep", "SELECT pg_sleep(10)", "FUNCTION_NOT_ALLOWED", None),
    ("PG_SLEEP", "SELECT PG_SLEEP(10)", "FUNCTION_NOT_ALLOWED", None),
    (
        "lo_import",
        "SELECT lo_import('/tmp/x')",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "set_config",
        "SELECT set_config('search_path', 'public', false)",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "current_setting",
        "SELECT current_setting('search_path')",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "txid_current",
        "SELECT txid_current()",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    ("version", "SELECT version()", "FUNCTION_NOT_ALLOWED", None),
    (
        "dblink",
        "SELECT * FROM dblink('host=evil', 'select 1') AS t(a int)",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "generate_series_from",
        "SELECT * FROM generate_series(1, 1000000000)",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "unnest",
        "SELECT * FROM orders WHERE id IN (SELECT unnest(ARRAY[1,2,3]))",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "repeat",
        "SELECT repeat('x', 100000000)",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "lpad",
        "SELECT lpad('x', 100000000)",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "string_agg",
        "SELECT string_agg(name, ',') FROM customers",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "pow_caret",
        "SELECT 2 ^ 1000000000",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    ("power", "SELECT power(2, 10)", "FUNCTION_NOT_ALLOWED", None),
    (
        "regex",
        "SELECT 'abc' ~ '(a+)+$'",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "cast_regclass",
        "SELECT 'pg_authid'::regclass",
        "CAST_NOT_ALLOWED",
        None,
    ),
    (
        "cast_regclass_fn",
        "SELECT CAST('pg_authid' AS regclass)",
        "CAST_NOT_ALLOWED",
        None,
    ),
    (
        "cast_oid",
        "SELECT 'shop.staff_salaries'::regclass::oid",
        "CAST_NOT_ALLOWED",
        None,
    ),
    (
        "cast_customers",
        "SELECT 'x'::shop.customers",
        "CAST_NOT_ALLOWED",
        None,
    ),
    (
        "cast_numeric_prec",
        "SELECT 1::numeric(10,2)",
        "CAST_NOT_ALLOWED",
        None,
    ),
    (
        "window",
        "SELECT id, count(*) OVER () FROM orders",
        "UNSUPPORTED_SYNTAX",
        None,
    ),
    (
        "filter",
        "SELECT count(*) FILTER (WHERE id > 1) FROM orders",
        "UNSUPPORTED_SYNTAX",
        None,
    ),
    (
        "lateral",
        "SELECT * FROM orders, LATERAL (SELECT 1) x",
        "UNSUPPORTED_SYNTAX",
        None,
    ),
    ("values", "SELECT * FROM (VALUES (1)) v(x)", "UNSUPPORTED_SYNTAX", None),
    (
        "tablesample",
        "SELECT * FROM orders TABLESAMPLE SYSTEM (1)",
        "UNSUPPORTED_SYNTAX",
        None,
    ),
    (
        "fetch",
        "SELECT * FROM orders OFFSET 0 ROWS FETCH FIRST 1 ROW ONLY WITH TIES",
        "UNSUPPORTED_SYNTAX",
        None,
    ),
    ("unicode", "SELECT U&'\\00A1'", "UNSUPPORTED_SYNTAX", None),
    ("escape", "SELECT E'\\x'", "UNSUPPORTED_SYNTAX", None),
    (
        "quoted_upper",
        'SELECT "UPPER"(name) FROM customers',
        "QUOTED_FUNCTION",
        None,
    ),
    ("email", "SELECT email FROM customers", "COLUMN_NOT_ALLOWED", None),
    (
        'select_"email"',
        'select "email" from customers',
        "COLUMN_NOT_ALLOWED",
        None,
    ),
    (
        "email_caps",
        'SELECT "Email" FROM customers',
        "COLUMN_NOT_ALLOWED",
        None,
    ),
    (
        "derived_email",
        "SELECT x.email FROM (SELECT id FROM customers) x",
        "COLUMN_NOT_ALLOWED",
        None,
    ),
    ("whole_row", "SELECT c FROM customers c", "WHOLE_ROW_REFERENCE", None),
    ("whole_row_table", "SELECT customers FROM customers", "WHOLE_ROW_REFERENCE", None),
    ("whole_row_count", "SELECT count(customers) FROM customers", "WHOLE_ROW_REFERENCE", None),
    ("whole_row_products", "SELECT products FROM products", "WHOLE_ROW_REFERENCE", None),
    (
        "having_max_email",
        "SELECT id FROM customers GROUP BY id HAVING max(email) > ''",
        "COLUMN_NOT_ALLOWED",
        None,
    ),
    (
        "having_min_email",
        "SELECT count(*) FROM customers HAVING min(email) = 'c1@example.test'",
        "COLUMN_NOT_ALLOWED",
        None,
    ),
    (
        "numeric_ok",
        "SELECT 1::numeric",
        "OK",
        'SELECT CAST(1 AS DECIMAL) AS "1" LIMIT 100',
    ),
    (
        "field_email",
        "SELECT (c).email FROM customers c",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "to_json_row",
        "SELECT to_json(c) FROM customers c",
        "FUNCTION_NOT_ALLOWED",
        None,
    ),
    (
        "limit_subquery",
        "SELECT id FROM orders LIMIT (SELECT 5)",
        "LIMIT_NOT_LITERAL",
        None,
    ),
    ("limit_all", "SELECT id FROM orders LIMIT ALL", "LIMIT_NOT_LITERAL", None),
    ("limit_null", "SELECT id FROM orders LIMIT NULL", "LIMIT_NOT_LITERAL", None),
    ("offset_5000", "SELECT id FROM orders OFFSET 5000", "OFFSET_NOT_ALLOWED", None),
    (
        "limit_rewrite",
        "SELECT * FROM orders LIMIT 100000",
        "OK",
        'SELECT "orders"."customer_id" AS "customer_id", "orders"."id" AS "id", "orders"."ordered_at" AS "ordered_at", "orders"."status" AS "status" FROM "shop"."orders" AS "orders" LIMIT 100',
    ),
    (
        "orders_caps",
        "select * from ORDERS",
        "OK",
        'SELECT "orders"."customer_id" AS "customer_id", "orders"."id" AS "id", "orders"."ordered_at" AS "ordered_at", "orders"."status" AS "status" FROM "shop"."orders" AS "orders" LIMIT 100',
    ),
    ("too_long", "SELECT " + "1" * 3994, "TOO_LONG", None),
    (
        "too_complex",
        "SELECT " + "+".join(["1"] * 300),
        "TOO_COMPLEX",
        None,
    ),
]


@pytest.mark.parametrize(("case_id", "sql", "expected", "expected_sql"), ATTACKS)
def test_attack_row(case_id: str, sql: str, expected: str, expected_sql: str | None) -> None:
    _ = case_id
    verdict = check(sql)
    assert verdict.code == expected
    if expected_sql is not None:
        assert verdict.sql == expected_sql
