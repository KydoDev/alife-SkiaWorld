# Test Report

Last run: 2026-11-10 — F2 Living environment + world seed (working tree before the F2 commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 80 tests) | 80 | 0 | 0 | 98.3% (`worldsim/`, excl. render) |
| Defaults-off light cycle vs F2 baseline (seed 1, 2000 steps, before the gene change) | 200/200 stats rows identical | | | |
| CI smoke commands (run, resume, form planet, image planet, resume of an image planet) | all complete | | | |
| Viewer (headless, `--planet examples/volcanic.json`, 5 frames + screenshot) | renders, panel complete | | | |
| Perf back-to-back, seed 1, 3k steps: F1 commit vs F2 tree | 303 vs 354 steps/s (no regression) | | | |

Lint: `ruff check .` — clean.

## Failures
None.
