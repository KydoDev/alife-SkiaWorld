# Test Report

Last run: 2026-11-11 - ADR-0012 piece 3 (procedural terrain in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 326 tests) | 326 | 0 | 0 | 98.94% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (18 golden sets; 44 terrains and 27 plumes; numpy mean on 34 lengths; seeding on 13 seeds) | 0 | | |

## Notes
- Terrain and plume digests equal at the first run. The pytest check recomputes every case except the two
  10 000-wide ones (time); the Rust test covers all of them. No step, loader or ABI change: benchmark and Unity
  tests not re-run.
