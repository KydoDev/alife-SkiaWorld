# Test Report

Last run: 2026-11-11 - ADR-0012 piece 4 (`World::new` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 340 tests) | 340 | 0 | 0 | 98.94% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (20 golden sets; 52 creations; 44 terrains and 27 plumes; numpy mean; seeding) | 0 | | |

## Notes
- Full `g2_golden.py --all` regeneration (2 min 18 s): the 18 existing `hashes.csv` and `terrain.json` unchanged.
- No step, loader or ABI change: benchmark and Unity tests not re-run.
