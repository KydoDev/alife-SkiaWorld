# Test Report

Last run: 2026-11-11 — ADR-0012 piece 1 (seeding in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 323 tests) | 323 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (18 golden sets; seeding vs CPython on 13 seeds; `genome_distance` on 700 pairs) | 0 | | |

## Notes
- No step, loader or ABI change: benchmark and Unity tests not re-run.
