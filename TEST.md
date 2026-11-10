# Test Report

Last run: 2026-11-10 — F5b Diet plasticity (working tree before the F5b commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 172 tests; new `tests/test_plasticity.py`) | 172 | 0 | 0 | 98.8% (`worldsim/`, excl. render) |
| Off-world identity: full-state fingerprints vs `c3e1c43` (default, day/night + sensing, F4, F5a, vents + rock) | identical | | | |
| Speed (default world, 2000 steps): off / on | 583 / 406 steps/s (before: 577) | | | |
| F5b positive control (`plastic_upkeep=0.2`, neutral; pre-registered >= 16/20) | 20/20: fires | | | |
| F5b cost-matched question (`plast_p` on vs neutral_cost, 20 pairs, 30k steps) | higher 19/20: beneficial | | | |
| F5b net selection (on vs neutral) / power at the real cost (neutral_cost < neutral) | 14/20, 15/20: not detected | | | |

Lint: `ruff check .` — clean.

## Failures
None at the end. The review's two regression tests (no-feeding-gene cell fed as a generalist; loader accepting a
moved diet in a frozen arm) failed before their fixes; the first experiment run was superseded. One new test compared a float distance to exactly 0 and failed on
rounding (~1e-16); the assertion now uses a tolerance.
