# Test Report

Last run: 2026-11-12 - ADR-0014 commit 2 (`sense_r`, save v9, kernel refuses `sense_range`), `main`, working tree
before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 366 tests) | 366 | 0 | 0 | 99.36% |
| `ruff check .` | clean | | | |
| Rust (`cargo test --locked`, `fmt --check`, `clippy -D warnings`) | all | 0 | 0 | |
| Golden regeneration (`g2_golden.py --all`, fresh root) | hashes and renders byte-identical | | | |

## Notes
- Unity EditMode was not run here: the parallel Unity session owns `unity/` right now. Its NativeWorldTests read
  the v9 golden root and need the DLL rebuilt (`scripts/unity_sync.py`) to pass.
