# Test Report

Last run: 2026-11-11 - ADR-0012 piece 5 (`ws_world_create`, ABI 2, Unity New world), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 342 tests) | 342 | 0 | 0 | 98.94% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (FFI 9 tests incl. creation; 20 golden sets; 52 creations; terrain; numpy mean; seeding) | 0 | | |
| Unity EditMode (batchmode, Unity 6000.5.6f1) | 10 | 0 | 0 | |

## Notes
- The New world button was not clicked on screen here (batchmode only): the owner's check.
- No step change: benchmark not re-run.
