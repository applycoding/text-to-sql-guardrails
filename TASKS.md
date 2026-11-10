# Tasks: text-to-sql-guardrails

Do the tasks in this order. A task is done when its acceptance check passes both locally and in CI. Criterion numbers refer to `PLAN.md` section 19.

Never weaken a test, a bound or an expected code to get a green run. Fix the code instead, or record a measured reason in `DEVIATIONS.md`.

## T1. Skeleton and CI lint job

- `pyproject.toml` (package `t2sql` under `src/`, ruff, mypy strict, pytest with `timeout = 30`).
- `requirements.txt` and `requirements-dev.txt` produced by `pip-compile --generate-hashes`, with the pins from PLAN section 3.
- `ci.yml` job `lint`: actions pinned by SHA, plus the SPDX, `uses:` SHA and LICENSE checks.
- Accept: criteria 12, 17, 18 and 20.

## T2. Schema, role and seed

- `sql/schema.sql` and `sql/roles.sql`, copied verbatim from PLAN sections 6 and 7.
- `src/t2sql/seed.py`, which applies both as admin with pg8000 and sets the reader password from `T2SQL_READER_PASSWORD`.
- `ci.yml` job `test` with the digest-pinned `postgres:17.11` service and `--locale=C`.
- Accept: the seed runs twice in a row without error, and `tests/test_db_layer.py` passes (criterion 5).

## T3. Guard

- `policy.py` (allow-lists, bounds, reason codes) and `guard.py` (stages 1–10 in PLAN section 8, plus `GuardConfig`). The guard is pure and imports nothing from the database layer.
- `tests/test_attacks.py` with every row of PLAN section 9, and `tests/test_differential.py`.
- Accept: criteria 1 and 8.

## T4. Dry run and executor

- `explain.py`, a pure plan evaluator.
- `executor.py`: one READ ONLY transaction, `SET LOCAL statement_timeout`, EXPLAIN, execute, byte cap, rollback, SQLSTATE mapping, and connection closing.
- `tests/test_explain.py`: synthetic plans plus the live pipeline rows; log the measured numbers.
- Accept: criteria 2 and 3.

## T5. Positive controls

- `tests/test_positive_controls.py`, implementing PLAN section 10 with a recording fake executor.
- Accept: criterion 4.

## T6. Model, pipeline, CLI

- `model.py` (`StubModel` and the factory), `adapters/openai_compat.py` (stdlib only, off by default), `pipeline.py` and `cli.py`.
- `conftest.py`: the network blocker, and the hook that fails the session on any skip, xfail or xpass.
- `tests/test_model.py`, `tests/test_cli.py`, `tests/test_eval.py` and `tests/fixtures/eval_expected.json`. Freeze the full rows from a CI run, and check them against the gold SQL.
- Accept: criteria 7, 9, 10 and 11.

## T7. Mutation check

- `tools/mutants.py` with M1–M12 from PLAN section 12, and `tests/test_mutant_targets.py`.
- `ci.yml` job `mutants`.
- Accept: criterion 6. The kill matrix is printed in the job log.

## T8. Browser demo

- `site/` (page, script, styles), `site/vendor.json` with the checksums, `tools/build_site.py`, `e2e/test_site.py` (Python Playwright 1.65.0), and the `ci.yml` job `site` that uploads the `site` artifact.
- Accept: criteria 13 and 14.

## T9. NOTICE, README, docs

- `NOTICE` (Arpan Bom, 2026, then third-party notices) and `tools/check_notice.py` (criterion 16).
- `README.md`: the demo label, what it does, how to run it locally (Postgres with `sql/*.sql`, then the CLI), the layers, honest limits (PLAN section 20), how this was verified, idea credits ("original implementation, inspired by" with links to `REFERENCES.md`), and the untested adapter note.
- `docs/verification.md`, mapping every criterion to its test and CI job.
- Accept: criterion 19.

## T10. Pages

- `pages.yml` as in PLAN section 17, with the post-deploy smoke check.
- Accept: criterion 15, once the change is merged to `main`.
