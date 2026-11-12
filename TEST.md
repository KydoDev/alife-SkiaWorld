# Test Report

Last run: 2026-11-12 - G3 P2b (whole world on screen, orientation, app version 0.0.1), `main`, working tree before
the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| pytest (367 tests) | 367 | 0 | 0 | 99.36% |
| Unity EditMode (batchmode, Unity 6000.5.6f1, StandaloneWindows64) | 22 | 0 | 0 | |
| Unity PlayMode, windowed Editor (3 tests) | 3 | 0 | 0 | |
| `ruff check .` | clean | | | |

## Notes
- New: `WorldCameraTests` rewritten for the fit-the-whole-world camera (no wrap, clamp and centre on both axes,
  margins refuse taps, `FollowFit` after a resize); `TheKernelCreatesTheDeepPortraitShape` (64x160 created, stepped,
  alive); PlayMode `FirstViewShowsTheWholeWorld` and `DrawnTileIsTheTappedTileAtThreeZoomsAndBothEdges`;
  pytest `test_write_config_writes_a_wide_and_a_deep_world_of_the_same_planet`.
- The Unity runs above came before the last edit (the version in the HUD title and `BuildAndroid -appVersion`);
  that edit compiled in the 0.0.1 Android build, but the Unity suites were not rerun after it.
- On the owner's phone: the build with the security-review fix shows the whole world ("funziona"). The 0.0.1 APK
  (the same code plus the version) is in Download, not yet installed when this was written.
- Not covered by tests: the screen-turn refit on a real device beyond the owner's check; the turn detection in
  `WorldSimView.FitView` is exercised only through `WorldCamera.FollowFit`.
