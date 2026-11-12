# Test Report

Last run: 2026-11-12 - G3 P1 (UI Toolkit shell for the Unity viewer), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unity EditMode (batchmode, Unity 6000.5.6f1, 16 tests) | 16 | 0 | 0 | |
| `ruff check .` | clean | | | |

## Notes
- Only `unity/` and docs change in this commit: Python (366 tests, 99.36%) and Rust were last green at ADR-0014
  commit 2 and the kernel is untouched.
- New: `ViewMathTests` (4), scale-to-fit placement and click-to-tile mapping. `CreateScene` ran in batchmode with no
  compiler or import errors; the scene's `UIDocument` points at `WorldSimPanel.asset` and `WorldSimView.uxml`.
- Not covered by tests: the UI in Play mode (buttons, keys, tool clicks, safe area). The owner checks it by hand.
