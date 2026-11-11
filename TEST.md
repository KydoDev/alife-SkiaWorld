# Test Report

Last run: 2026-11-11 — G2 M5 item 6 (`sensing` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 281 tests) | 281 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (12 golden sets; `genome_distance` vs Python on 700 pairs; loader bounds for every ported propensity) | 0 | | |
| `sensing`, `sensing_volcanic` sets, kernel vs Python | equal at all 1000 steps | | | |
| Earlier ten sets' `hashes.csv`, regenerated | byte-identical | | | |
| M3 benchmark vs previous commit, 2 alternating rounds | 800 cells +1%, 10k +4%, 50k -1% (noise level) | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.
