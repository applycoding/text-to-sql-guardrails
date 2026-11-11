# text-to-sql-guardrails

**demo, deterministic offline model, not a production security boundary**

Natural-language questions become one PostgreSQL `SELECT` over the small `shop` demo schema. Every query passes three layers before execution:

1. **Parser allow-list** (sqlglot AST): statement types, tables, columns, functions, casts, and `LIMIT`.
2. **`EXPLAIN` dry run**: planner cost and row estimates with fixed upper bounds.
3. **Read-only execution** as `t2s_reader` on a digest-pinned PostgreSQL 17.11 image.

The default model is a deterministic offline template stub. CI sets no API key and blocks outbound network access except Postgres.

### Run locally

Requirements: Python 3.13, PostgreSQL 17.x.

```bash
pip install -r requirements-dev.txt
pip install -e .
export T2SQL_DSN_ADMIN_PASSWORD=...
export T2SQL_READER_PASSWORD=ci_reader
python -m t2sql.seed
python -m t2sql ask "how many customers in Denver?"
python -m t2sql check --sql "SELECT id FROM orders"
```

### Honest limits

- The stub is five regex templates, not a language model. CI measures nothing about LLM accuracy.
- The optional OpenAI-compatible adapter (`T2SQL_MODEL=openai-compatible`) is **untested in CI** and makes no accuracy claim.
- The policy is a deliberately small SQL subset for one demo schema, not a complete PostgreSQL security boundary.
- `EXPLAIN` estimates can be wrong and vary by version and settings.
- Role defaults are reinforced per transaction in the executor; catalog reads are blocked in the AST, not by grants.
- The browser demo runs AST checks only; row payloads are precomputed in CI.

### How this was verified

See [docs/verification.md](docs/verification.md) for all 20 success criteria mapped to tests and CI jobs. The regression check is **10/10 stub executable questions** and **5/5 refusals** (`tests/test_eval.py`).

### Credits

Original implementation, inspired by the public work listed in [REFERENCES.md](REFERENCES.md).

License: Apache-2.0. Author: Arpan Bom.
