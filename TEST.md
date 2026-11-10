# Test Report

Last run: 2026-11-10 — F3 re-run at the P1 standard (branch `exp/f3-p1` on `bb39ba3`)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 197 tests) | 197 | 0 | 0 | 98.9% (`worldsim/`, excl. render) |
| Reproducibility on main after #19 (libm light): `flat_seasons` seed 1 `free`, 30k steps, re-run | identical CSV row | | | |
| F3 P1 positive control (`sense_upkeep=0.5`; pre-registered >= 16/20) | 16/20, then 19/20 on seeds 21–39: fires | | | |
| F3 P1 phototaxis (`w_light` free vs off) | 13/20, then 16/20: lean, not established | | | |

Lint: `ruff check .` — clean.

## Failures
None. No engine code changed in this piece (experiment script and docs only).
