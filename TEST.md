# Test Report

Last run: 2026-11-12 - ADR-0014 commit 1 (trait table refactor), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 352 tests) | 352 | 0 | 0 | 99.32% |
| `ruff check .` | clean | | | |
| Golden regeneration (`g2_golden.py --all`, fresh root) | every file byte-identical | | | |

## Notes
- No Rust or Unity change in this commit: the Rust suite was last green at ADR-0013 piece 4 (25556cd), Unity
  EditMode 12/12 at piece 5 (19f0815).
