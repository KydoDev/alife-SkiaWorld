# Test Report

Last run: 2026-11-11 — G2 M5 item 7 (`open_genome` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 294 tests) | 294 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (14 golden sets; `genome_distance` vs Python on 700 pairs; loader bounds for every ported propensity and the rule genes) | 0 | | |
| `open_genome`, `rules_neutral` sets, kernel vs Python | equal at all 1000 steps | | | |
| Earlier twelve sets' `hashes.csv`, regenerated | byte-identical | | | |
| M3 benchmark vs previous commit, alternating rounds | means of six rounds, 800 cells 0%, 10k +2%, 50k -2% (the first three rounds showed 50k -9%, the next three, run in the other order, +4%: noise level); Cell grows from 384 to 408 bytes (the rule Vec) | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.
