# Test Report

Last run: 2026-11-11 — G2 M5 item 2 (`defence` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 228 tests) | 228 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (golden sets `default`, `volcanic`, `defence`, `defence_neutral`; loader bounds on a defence save) | 0 | | |
| `defence` and `defence_neutral` sets, kernel vs Python | equal at all 1000 steps | | | |
| `default`, `volcanic` `hashes.csv` regenerated | byte-identical | | | |
| M3 benchmark (default flags), before / after | 6.38 / 6.11, 8.08 / 7.92, 5.43 / 5.54 M cell-updates/s | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.
- The review also ran a reseed-after-extinction world with armour against the kernel (scratch, not committed): equal.
