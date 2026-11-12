# Test Report

Last run: 2026-11-12 - G3 P4 (ABI 4 kernel views, ADR-0016), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| pytest (379 tests) | 379 | 0 | 0 | 99.38% |
| `cargo test --release` (`engine-rs`, 53 tests) | 53 | 0 | 0 | |
| `cargo fmt --check`, `cargo clippy --all-targets --release -D warnings` | clean | | | |
| Unity EditMode (batchmode, Unity 6000.5.6f1, StandaloneWindows64) | 26 | 0 | 0 | |
| Unity PlayMode, windowed Editor (3 tests) | 3 | 0 | 0 | |
| `ruff check .` | clean | | | |

## Notes
- New: `tests/test_views.py` (kind, energy and chem levels with NaN, infinities and a zero `div_thr`, the word
  layout, the key wrap and top byte, the cell record and colony size, read-only, the committed `views.json` equals
  this Python - xfail when made on another OS, since libm may differ); Rust `views::tests` (twins of the edge
  cases and the key wrap) and `golden_views.rs` (tiles, records and light factor equal `views.json`; the state hash
  is unchanged; an empty tile is absent and a tile outside is refused); Unity `ViewTests` (struct sizes 56 and 248,
  the vectors through P/Invoke, a hand-built `Tile` with byte 3 = 0xFF).
- The Rust views matched Python byte for byte on all four golden sets (default, volcanic, plasticity, combined).
- Not covered: the `CellRecord` marshaling (`ByValArray`) under IL2CPP on a device - EditMode runs on Mono only.
  P4 ships no APK; the first P6 build on the phone checks it. P6 should call `Cell()` once per selection, not per
  frame.
