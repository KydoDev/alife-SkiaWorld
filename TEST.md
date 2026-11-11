# Test Report

Last run: 2026-11-11 — G2 M5 item 4 (`plasticity` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 254 tests) | 254 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (8 golden sets; loader bounds for `plast_p`, diet, `hgt_p`, `armor_p`) | 0 | | |
| `plasticity`, `plastic_neutral` sets, kernel vs Python | equal at all 1000 steps and in both renders | | | |
| Earlier six sets' `hashes.csv`, regenerated | byte-identical | | | |
| M3 benchmark vs previous commit, 3 alternating runs | 800 +9%, 10k -4%, 50k -3% | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged (the render change is covered by the golden renders).
