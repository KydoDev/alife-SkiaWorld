# Test Report

Last run: 2026-11-11 - ADR-0013 piece 4 (`ws_world_intervene`, ABI 3, nutrient cap), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 344 tests) | 344 | 0 | 0 | 98.94% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (FFI 12 incl. interventions and 17 refusals; interventions 6 incl. the cap regression; 20 golden sets; 52 creations) | 0 | | |
| Unity EditMode (batchmode, Unity 6000.5.6f1) | 12 | 0 | 0 | |

## Notes
- Edits run between steps: step loop untouched, benchmark not re-run.
