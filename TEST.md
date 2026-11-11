# Test Report

Last run: 2026-11-11 - ADR-0012 piece 2 (numpy pairwise mean in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 324 tests) | 324 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (18 golden sets; numpy mean on 34 lengths; seeding on 13 seeds) | 0 | | |

## Notes
- First candidate (accumulator seeded with the first element) failed at n = 4; the identity-seeded sum is the one
  committed. No step, loader or ABI change: benchmark and Unity tests not re-run.
