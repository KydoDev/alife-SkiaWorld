# Test Report

Last run: 2026-11-12 - G3 P3 (Android spike), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| pytest (366 tests) | 366 | 0 | 0 | 99.36% |
| Unity EditMode (batchmode, Unity 6000.5.6f1, StandaloneWindows64) | 19 | 0 | 0 | |
| Unity PlayMode, windowed Editor (2 tests) | 2 | 0 | 0 | |
| Device check on POCO F2 Pro (`android_check.py`, 2 golden sets) | 2 ran | | | |
| `ruff check .` | clean | | | |

## Notes
- Device check (release IL2CPP APK, kernel only): default 7991 steps/s, volcanic 5574 steps/s. Golden hashes are
  **not comparable** on ARM: default diverges from the Windows/Python reference at step 246, volcanic at step 201.
  A divergence is reported, never tolerated (G2_PLAN "Golden sets per platform"); it is not a failure.
- One PlayMode run earlier in the piece failed `VirtualInputReachesTheView` (the virtual click landed elsewhere, on a
  1623x913 Game view), right after the project came back from the Android target. Two later windowed runs, the last
  one after the security-review fixes, passed 2/2. Treated as intermittent; watch it.
- The viewer APK, rebuilt after the review, requests no permissions (`aapt dump permissions`: only Unity's own
  `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`). That rebuilt APK has not been run on the phone yet.
- Rust untouched in this piece except the build target; the arm64 `.so` has 16 KB-aligned LOAD segments.
- Not covered by tests: real touch (pinch, two-finger pan, tap) on the device, which waits for the owner's check.
