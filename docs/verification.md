# Verification map

| Criterion | Tests | CI job |
| --- | --- | --- |
| 1 | tests/test_attacks.py | test |
| 2 | tests/test_explain.py::test_live_bounds | test |
| 3 | tests/test_explain.py | test |
| 4 | tests/test_positive_controls.py | test |
| 5 | tests/test_db_layer.py | test |
| 6 | tools/mutants.py | mutants |
| 7 | tests/test_eval.py | test |
| 8 | tests/test_differential.py | test |
| 9 | tests/test_model.py | test, lint |
| 10 | tests/test_cli.py | test |
| 11 | conftest skip hook, lint grep | test, lint |
| 12 | ruff, mypy | lint |
| 13 | e2e/test_site.py | site |
| 14 | tools/build_site.py checksums | site |
| 15 | .github/workflows/pages.yml | pages (on main) |
| 16 | tools/check_notice.py | lint |
| 17 | SPDX lint step | lint |
| 18 | LICENSE sha256 step | lint |
| 19 | README sections | lint (grep) |
| 20 | action pin check | lint |
