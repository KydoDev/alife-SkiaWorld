# Test Report

Last run: 2026-11-11 — G2 M5 item 8 (combined golden sets), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 322 tests) | 322 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (18 golden sets; `genome_distance` vs Python on 700 pairs; loader bounds and the rule budget) | 0 | | |
| `combined`, `combined_reseed`, `combined_width2`, `open_genome_unsensed`, kernel vs Python | equal at all 1000 steps | | | |
| Earlier fourteen sets' `hashes.csv`, regenerated | byte-identical | | | |

## Notes
- No kernel code changed: benchmark not re-run. Unity EditMode tests not re-run (C ABI and `unity/` unchanged).
