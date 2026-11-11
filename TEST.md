# Test Report

Last run: 2026-11-11 — F5e prey defence (branch `feat/f5e-prey-defence`), working tree before the docs commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 211 tests; new `tests/test_defence.py`, 13 tests) | 211 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (14 tests) | 0 | | |
| Golden sets regenerated for save v8 (default + volcanic) | `hashes.csv` unchanged | | | |
| Off-world fingerprints, 8 configurations, vs `36b4d21` | identical | | | |
| Speed, default world (best of 3, 1500 steps) | main 574, defence off 555, on 530 steps/s | | | |

## Notes
- Off vs main speed differs by about 3%, within run-to-run noise on this machine; the predation branch gains
  one boolean test.
- Experiment results are in `docs/ROADMAP.md` (F5e), not here.
