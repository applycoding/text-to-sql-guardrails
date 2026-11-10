# text-to-sql-guardrails

**Demo, deterministic offline model, not a production security boundary.**

Natural-language questions become one PostgreSQL `SELECT` over a small demo schema. A query runs only after three layers accept it:

1. a parser-based allow-list (sqlglot AST: statement types, tables, columns, functions, casts, LIMIT);
2. an `EXPLAIN` dry run with cost and row bounds;
3. execution as a read-only database role.

Every refusal has a fixed, tested reason code. The default model is a template stub with no network access and no API key. See `PLAN.md`.

Original implementation, inspired by the public work listed in `REFERENCES.md`.

License: Apache-2.0. Author: Arpan Bom.
