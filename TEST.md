# Test Report

Last run: 2026-11-11 - ADR-0013 piece 2 (`refresh_terrain` refactor), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 342 tests) | 342 | 0 | 0 | 98.94% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (20 golden sets with renders; 52 creations; FFI 9) | 0 | | |

## Notes
- Load path only (`from_parts`): step loop untouched, benchmark not re-run; Unity not re-run (no ABI change).
