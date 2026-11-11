# Test Report

Last run: 2026-11-11 — World study (branch `exp/world-study`, stacked on `exp/f3-p1`)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 198 tests) | 198 | 0 | 0 | 98.85% (`worldsim/`, excl. render) |
| World study coarse sweep (9 settings x 4 runs, 10k) | no setting meets the criteria | | | |
| Extended sweep with `spec_exp` (12 settings x 4 runs, 10k) | no setting meets the criteria | | | |
| Check of the closest setting (20 P1 pairs, 30k; predator criterion relaxed post hoc) | 7/20 pass: rejected | | | |

Lint: `ruff check .` — clean.

## Failures
None. No engine code changed in this piece (study script and docs only).
