# Test Report

Last run: 2026-11-10 — F5c Horizontal gene transfer (working tree before the F5c commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 195 tests; new `tests/test_hgt.py`) | 195 | 0 | 0 | 98.9% (`worldsim/`, excl. render) |
| Rust `cargo test` + `tests/test_g2_golden.py` after the v7 golden regeneration | green / 10 passed | 0 | | `hashes.csv` unchanged |
| Off-world identity: full-state fingerprints vs `367aecd` (default, day/night + sensing, F4, F5a, vents + rock, F5b on) | identical | | | |
| Speed (default world, idle machine): off / on | 539–560 / ~526 steps/s (before: 543–560) | | | |
| F5c positive control (`hgt_upkeep=0.2`, neutral; pre-registered >= 16/20) | 20/20: fires | | | |
| F5c cost-matched (`hgt_p` on vs neutral_cost) | 10/20; confirmation 13/20 lower: no detectable effect | | | |
| F5c net selection (on vs neutral) | lower 16/20; confirmation 18/20: selected against | | | |

Lint: `ruff check .` — clean.

## Failures
None at the end. During the work: the six G2 golden tests failed as expected after the save bump to v7 and
passed after regenerating the golden sets. The review found no defect; its notes added one loader check and
one test.
