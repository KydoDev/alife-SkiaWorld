# Test Report

Last run: 2026-11-10 — F1 Foundations (working tree before the F1 commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 27 tests) | 27 | 0 | 0 | 98.7% (`worldsim/`, excl. render) |
| Exit demo: seed 1, 10k steps vs resume at 5k (separate processes) | final saves identical, 500/500 stats rows identical | | | |
| Observer purity: 3000-step run with tracker vs pre-tracker baseline | 300/300 rows identical on existing columns | | | |
| E2E (viewer, headless screenshot incl. `--load`) | renders, panel complete | | | |

Lint: `ruff check .` — clean.

## Failures
None.
