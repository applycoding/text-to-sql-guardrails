# References: text-to-sql-guardrails

These references are for ideas and documentation only. No source, test, dataset, figure or text from them is copied, translated or vendored into this repo.

Licenses were checked on 2026-11-10 against each project's license file or its licence page.

The outbound license for this repo is Apache-2.0. The libraries that are actually used as dependencies (sqlglot, pg8000, Pyodide and others) are listed with versions and licenses in `NOTICE`. They are not repeated here.

## Not a duplicate of these applycoding repos

| Repo | Difference |
| --- | --- |
| [agent-guardrails-observability](https://github.com/applycoding/agent-guardrails-observability) | A LangGraph agent with tool guardrails, tracing and red-team prompts. This repo has no agent runtime. Its guardrails act on SQL syntax trees and on database plans and privileges. |
| [llm-rag-api](https://github.com/applycoding/llm-rag-api), [rag-llm-eval-demo](https://github.com/applycoding/rag-llm-eval-demo) | Retrieval QA over documents. This repo has no retrieval. Its answers come from a relational database. |
| [llm-eval-observability](https://github.com/applycoding/llm-eval-observability) | Prompt and LLM evaluation and tracing. This repo makes no LLM accuracy claim. Its eval is a fixed regression check of a template stub. |
| [multi-agent-langgraph-workflow](https://github.com/applycoding/multi-agent-langgraph-workflow), [support-ticket-agent](https://github.com/applycoding/support-ticket-agent) | Multi-step agent workflows. This repo does one question to one query, with no orchestration. |

## Idea references

### 1. Spider (text-to-SQL benchmark)

- Paper: Yu et al., "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task", arXiv:1809.08887.
- Site: https://yale-lily.github.io/spider. The code repo https://github.com/taoyds/spider is Apache-2.0, and the dataset is CC BY-SA 4.0.
- Idea used: score a query by comparing its **execution result** with the result of a gold query, instead of comparing SQL strings. The dataset is not used.

### 2. BIRD (text-to-SQL benchmark)

- Paper: Li et al., "Can LLM Already Serve as A Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs", arXiv:2305.03111.
- Site: https://bird-bench.github.io/. The dataset is CC BY-SA 4.0.
- Idea used: execution accuracy, and the point that the cost of a generated query matters as well as its correctness. Here that becomes the `EXPLAIN` cost bound. No data is used.

### 3. sqlglot documentation and optimizer

- Docs: https://sqlglot.com/sqlglot.html
- Source: https://github.com/tobymao/sqlglot, tag `v30.31.0` (`447a8a8929835a82ead76d7c6d7e104df344ab36`). License: MIT.
- Idea used: parse SQL into a typed AST, and resolve columns with `optimizer.qualify` against a restricted schema. sqlglot is also a runtime dependency (see `NOTICE`). No sqlglot code is copied.

### 4. PostgreSQL documentation

- `EXPLAIN`: https://www.postgresql.org/docs/17/sql-explain.html
- Privileges: https://www.postgresql.org/docs/17/ddl-priv.html
- `statement_timeout`, `default_transaction_read_only` and `search_path`: https://www.postgresql.org/docs/17/runtime-config-client.html
- License: PostgreSQL License, https://www.postgresql.org/about/licence/
- Ideas used: a read-only role with column-level grants, a per-transaction statement timeout, and plan cost and row estimates used as a pre-execution bound.

### 5. OWASP SQL Injection Prevention Cheat Sheet

- URL: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html. The repo https://github.com/OWASP/CheatSheetSeries is CC BY-SA 4.0.
- Ideas used: least-privilege database accounts, and allow-list input validation as defence in depth. No text is copied.

### 6. Vanna (open-source text-to-SQL library)

- URL: https://github.com/vanna-ai/vanna (HEAD `365d0617c1a4`, checked 2026-11-10). License: MIT.
- Idea used: the general shape of a question-to-SQL-to-rows pipeline. This repo does not use Vanna, and none of its code was read for the implementation.

### 7. Pyodide

- Docs: https://pyodide.org/en/stable/usage/api/js-api.html. Source: https://github.com/pyodide/pyodide, tag `314.0.7`. License: MPL-2.0.
- Used as a runtime for the browser demo; it is listed in `NOTICE`. Idea used: run the same Python guard in the browser, with self-hosted assets and no CDN.
