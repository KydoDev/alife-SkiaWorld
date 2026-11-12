# Test Report

Last run: 2026-11-12 - G3 P2 (camera, Input System), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unity EditMode (batchmode, Unity 6000.5.6f1, 19 tests) | 19 | 0 | 0 | |
| Unity PlayMode, windowed Editor (2 tests) | 2 | 0 | 0 | |
| Unity PlayMode, batchmode (2 tests) | 1 | 0 | 1 (mouse test, by design) | |
| `ruff check .` | clean | | | |

## Notes
- Only `unity/` and docs change in this commit: Python (366 tests, 99.36%) and Rust were last green at ADR-0014
  commit 2 and the kernel is untouched.
- `VirtualMouseReachesThePanel` skips itself in batchmode: with no window UI Toolkit gives runtime panels no input
  (checked while writing it: the virtual mouse got its events, the panel none). It passes in a windowed Editor.
- Not covered by tests: real touch (pinch, two-finger pan) on a device, which waits for P3; the owner checks pan and
  zoom with a mouse in the Editor.
