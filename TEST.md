# Test Report

Last run: 2026-11-11 — G2 M5 item 3 (`hgt` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 241 tests) | 241 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (golden sets `default`, `volcanic`, `defence`, `defence_neutral`, `hgt`, `hgt_neutral`; loader bounds for `armor_p` and `hgt_p`) | 0 | | |
| `hgt`, `hgt_neutral` sets, kernel vs Python | equal at all 1000 steps | | | |
| Earlier four sets' `hashes.csv`, regenerated | byte-identical | | | |
| M3 benchmark, this build vs previous commit side by side | equal within noise (50k slower for both: machine state) | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.
