# Test Report

Last run: 2026-11-11 — G2 M4 part B (Unity front-end), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 211 tests) | 211 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Unity EditMode (`unity/`, batchmode, Unity 6000.5.6f1) | 7 | 0 | 0 | |
| Rust (`engine-rs`) | not re-run: unchanged since the last green run (M4 part A) | | | |

## Notes
- Unity tests: ABI version; golden hashes through P/Invoke in uneven chunks (default, volcanic); start render
  equal to Python's byte for byte (default, volcanic); bad save and short buffer raise with the kernel message;
  disposed world throws. Not in CI (Unity needs a licence): run locally (DEVELOPER_GUIDE, Unity front-end).
- Windows player build checked on screen via screenshots (surface on top, play/pause/step/speed). One unexplained
  pause after a click on `+` then `Space`, not reproduced in two tries; recorded in G2_PLAN, not a test failure.
