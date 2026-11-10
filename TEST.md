# Test Report

Last run: 2026-11-10 — G2 M2 open points (vent field, seabed, gradient off numpy; CI `--locked` + audit), working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 198 tests; new `test_terrain_transcendentals_come_from_libm`) | 198 | 0 | 0 | 98.85% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (14 tests) | 0 | | |
| `cargo deny --locked check advisories` (cargo-deny 0.20.2, default config) | advisories ok | | | |
| Golden sets regenerated (default + volcanic, 1000 steps) vs committed | identical (`hashes.csv`, `rng.json`, decompressed `start.json.gz`) | | | |
| Old vs new expressions (plumes with x-wrap, `seabed_heights` x150 seeds, `planet.png` gradient) | bit-identical | | | |

## Notes
- The new regression test cannot fail on this CPU (no AVX-512: numpy already used libm); it guards
  the Linux CI runner.
