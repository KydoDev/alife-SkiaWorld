# Test Report

Last run: 2026-11-13 - G3 P8 piece 4 (Unity species drawer); cargo from the piece 3 run (no Rust change since),
`main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| pytest (429 tests) | 429 | 0 | 0 | 99.53% |
| `cargo test --release` (`engine-rs`, 74 tests) | 74 | 0 | 0 | |
| `cargo fmt --check`, `cargo clippy --all-targets --release -D warnings` | clean | | | |
| Unity EditMode (batchmode, Unity 6000.5.6f1, StandaloneWindows64) | 61 | 0 | 0 | |
| Unity PlayMode, windowed Editor (9 tests) | 9 | 0 | 0 | |
| `ruff check .` | clean | | | |

## Notes
- New in P8 piece 4: EditMode `SpeciesListTests` (5: row order and cap, row text, tracked and untracked header,
  ancestry to the root and to a forgotten ancestor, distinct tints) and species in `CellSheetTests`; PlayMode
  `SpeciesDrawerListsTheSpeciesAndShowsAnAncestry` (tracked save: drawer equals the kernel's list and ancestry,
  the drawer and the population panel close each other) and `AnUntrackedWorldSaysItHasNoSpecies`.
- New in P8 piece 3: `tests/ffi.rs` (3: species of the created and loaded cases through the ABI, refusals and
  out-untouched, species tile key) and the ABI 6 entries in the poisoning unit test; EditMode `SpeciesTests` (5)
  and the new struct layouts in `ViewTests`. PlayMode rerun (7/7) on the ABI 6 DLL.
- New in P8 piece 2: `engine-rs/tests/golden_species.rs` (3: the six `species.json` cases sample by sample and
  field by field, a tracked and an untracked save, 13 refused trackers), 4 unit tests in `species.rs` (pruning
  cascade, novelty, `restore` refusals, origins) and one in `views.rs` (species key); `golden_save.rs`'s skipped-
  parts test now expects a malformed tracker to be refused. Mutations of the extinction step and of `now` fail.
- New in P8 piece 1: `tests/test_species_vectors.py` (7: committed `species.json` and tracked save regenerate
  identically, digest layouts, final dump equals last digest, vacuous cases refused, tracking leaves the hash) and
  `test_an_untracked_world_keys_tiles_by_lineage`; the tile-word test now expects the species key on tracked worlds.
- New in P7 piece 4: EditMode `GameTextTests` (3) and PlayMode `ToolsSpendTheGamesEnergyAndAMilestoneIsToasted`.
  pytest lost two tests with the `game_tools.json` export they covered (the rules now come from the kernel).
- New in P7 piece 3: `tests/ffi.rs` (3: default rules, the 8 game cases through the ABI in chunks, refusals),
  `golden_games.rs` (the day-length cap), EditMode `GameTests` (3) and the struct offsets in `ViewTests`. PlayMode
  not rerun: no view code changed (piece 4 moves the tools onto the game).
- New in P7 piece 2: `engine-rs/tests/golden_games.rs` (6): the 8 `games.json` cases field by field, including
  the per-check trace of measures and every `hashes.csv` row of the idle games; tool and milestone names; default
  rules; rule validation; a kernel refusal and an off-world or unaffordable action leave the game unchanged. A
  mutation check (specialist cut, vent distance, colony size, smoothing, collapse window, dip) now fails on each
  mutation except one that is equivalent by construction (survivor without the dip).
- New in P7 piece 1: `tests/test_game_vectors.py` (5): defaults, committed `games.json`, idle hashes equal
  `hashes.csv`, the generator refuses vacuous cases, integer distance equals `math.hypot` on a grid of offsets.
  pytest now takes about 2 minutes (the game vectors are rebuilt once, about 15 s).
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
