# Test Report

Last run: 2026-11-13 - G3 P6b (population panel), `main`, working tree before the commit; pytest and cargo from the
save-loader run (no Python or Rust change since)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| pytest (418 tests) | 418 | 0 | 0 | 99.39% |
| `cargo test --release` (`engine-rs`, 53 tests) | 53 | 0 | 0 | |
| `cargo fmt --check`, `cargo clippy --all-targets --release -D warnings` | clean | | | |
| Unity EditMode (batchmode, Unity 6000.5.6f1, StandaloneWindows64) | 45 | 0 | 0 | |
| Unity PlayMode, windowed Editor (6 tests) | 6 | 0 | 0 | |
| `ruff check .` | clean | | | |

## Notes
- New in P6b: `PopulationTests` (4 golden worlds + the bounded history) and PlayMode
  `PopulationPanelShowsTheCountsAndTheirHistory`.
- New in P6a: `CellSheetTests` (4: names equal `worldsim/world.py`, kind rule, summary text, following across
  the seam) and PlayMode `TappingACellOpensItsSheetAndTheSheetFollowsIt` (a second copy of the golden world says
  where the cell is after one step).
- APK 0.0.2 (P5) is on the owner's phone, not yet checked (frame time, look).
- New in P5c/P5d: `DaylightIsNeonUpToTheMeanLightAndDayFromTwiceIt`, `BackdropTests` (2), and the PlayMode first-view
  test now checks that the backdrop covers the view under the world. The sprite PlayMode test caught the sprite
  layer being inserted under the world once the backdrop existed; fixed before the commit.
- New in P5b: `SpriteLayerTests` (every pixel of the GPU sprite layer equals a CPU version of the rules on the
  default, plasticity and volcanic golden saves, both frames, night and day palettes; 10-13 starving and 147-352
  bonded cells per world, so those branches are exercised) and PlayMode `SpritesAppearFromFivePixelsPerTileOverTheWorld`.
  Only on this machine's GPU (Windows Editor): Unity is not in CI, and the phone's GPU is checked by the owner (P5 APK).
- New in P5a: `SpriteArtTests` (sprites and palette equal the design table in `docs/G3_PLAN.md`, atlas roles and
  palette texels where the shader reads them).
- New: `test_load_bounds_ids_ages_lineages_and_counters_like_the_kernel` (30 cases: id, age, lineage, step_count,
  next_id and a counter at 2^62 + 1, -1, 1.5, True and "7"), the largest values accepted, and a `next_id` below a
  cell id refused. Written first; 27 of them failed before the fix. After the security review: `next_id` equal to
  the newest cell id loads; tile coordinates and bond ids must be JSON integers; tracker counters and `next_id` are
  bounded; a huge hostile value is not echoed in the message.
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
