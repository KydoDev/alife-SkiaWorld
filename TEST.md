# Test Report

Last run: 2026-11-11 — G2 M4 part A (C ABI and render in Rust), branch `feat/g2-m4-unity`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 211 tests) | 211 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (23 tests; new `tests/ffi.rs` 6, `tests/golden_render.rs` 2, `ffi` unit 1) | 0 | | |
| Golden renders (`render_start`, `render_end`) vs Rust, both sets | equal byte for byte | | | |
| `hashes.csv` after computing light at load | unchanged | | | |
| Built `worldsim_core.dll` called from Python `ctypes` (volcanic, 1000 steps) | hash equal to `hashes.csv` | | | |

## Notes
- No Python engine change: `scripts/g2_golden.py` only gains the two renders (`--renders-only`).
- Security review of the C ABI: no blocking issue; follow-ups applied (bounded error messages, shared references for read-only calls, no panic in error handling, `panic = "abort"` refused at compile time).
