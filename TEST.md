# Test Report

Last run: 2026-11-10 — after `fix(engine): make runs deterministic per seed`

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit (`tests/test_world.py`) | 12 | 0 | 0 | 98% (`worldsim/`, excl. render) |
| Integration (headless run, seed 1, 1000 steps, two processes) | `stats.csv` byte-identical | | | |
| E2E (viewer, manual) | not run | | | |

Lint: `ruff check .` — clean.

## Failures
None.
