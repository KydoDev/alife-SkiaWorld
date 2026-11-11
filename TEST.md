# Test Report

Last run: 2026-11-11 - ADR-0013 piece 5 (Unity sandbox tools, `game_tools.json` export), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 346 tests) | 346 | 0 | 0 | 98.94% |
| `ruff check .` | clean | | | |
| Unity EditMode (batchmode, Unity 6000.5.6f1) | 12 | 0 | 0 | |

## Notes
- No Rust change: the Rust suite was last green at piece 4 (25556cd).
- The tool bar and click-to-apply were not exercised on screen here (batchmode only): the owner's check.
