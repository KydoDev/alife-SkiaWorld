# Test Report

Last run: 2026-11-11 — G2 M5 item 5 (`sex` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 267 tests) | 267 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (10 golden sets; `genome_distance` vs Python on 700 pairs, 80 with a subnormal maximum; loader bounds for every ported propensity) | 0 | | |
| `sex`, `sex_neutral` sets, kernel vs Python | equal at all 1000 steps | | | |
| Earlier eight sets' `hashes.csv`, regenerated | byte-identical | | | |
| CPython `vector_norm` re-implementation vs `math.dist` (scratch, 2M pairs) | 0 mismatches | | | |
| M3 benchmark vs previous commit, 2 alternating rounds | 800 +2%, 10k -5%, 50k +2% | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.
