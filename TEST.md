# Test Report

Last run: 2026-11-11 - ADR-0013 piece 3 (`World::intervene`, interventions golden kind), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 344 tests) | 344 | 0 | 0 | 98.94% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (interventions: 5 cases, 30 actions, non-vacuous; 5 refusal tests; 20 golden sets with renders; 52 creations; FFI 9) | 0 | | |

## Notes
- Full `g2_golden.py --all` into a fresh root: all 20 `hashes.csv`, `terrain.json`, `create.json` and
  `interventions.json` byte-identical to the committed files.
- Step loop untouched (edits run between steps): benchmark not re-run; no ABI change, Unity not re-run.
