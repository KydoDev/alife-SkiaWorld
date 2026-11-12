# PLAN

G2 M5, second half: world creation and interventions in the kernel, as decided in ADR-0012 and ADR-0013 (both
accepted 2026-11-11; world creation first). Work on `main`, one commit per piece, push only with the owner's OK.
Verdicts, cases and non-vacuous conditions are fixed in the ADRs, before any run; detail: `docs/G2_PLAN.md`.

## Checklist
1. [x] ADR-0012 piece 1: CPython integer and string seeding in `rng.rs`; raw-state golden vectors
2. [x] ADR-0012 piece 2: numpy pairwise mean (`numpy_mean`), bit-equal to `ndarray.mean()` on the fixed lengths
3. [x] ADR-0012 piece 3: `generate_terrain` (incl. `vent_plume`); terrain digest equal on every listed case
4. [x] ADR-0012 piece 4: `World::new`; step-0 hashes and creation sets `create_default`, `create_volcanic`
5. [x] ADR-0012 piece 5: `ws_world_create`, ABI 2, FFI tests, Unity "new world"; security review first
6. [x] ADR-0013 piece 2: `refresh_terrain` refactor; all hashes and renders unchanged
7. [x] ADR-0013 piece 3: `World::intervene` with validation; interventions golden kind; `play.replay` pytest
8. [x] ADR-0013 piece 4: `ws_world_intervene`, `WS_ERR_INVALID`, ABI 3, FFI tests; security review first
9. [x] ADR-0013 piece 5: Unity sandbox tools from exported `GameRules()` parameters (checked by hand)
10. [x] Owner's idea (2026-11-11, as soon as possible): evolvable perception radius `sense_r` (see below)
11. [ ] Owner's idea: obstacles and scattered resources; PARKED 2026-11-12 as a hypothesis to revisit (item 10 null)
12. [x] ADR-0014: trait table first, then `sense_r`; the kernel refuses `sense_range` until validated
13. [x] Item 10, commit 1: trait table refactor (Python); every golden file byte-identical, steps/s measured
14. [x] Item 10, commit 2: `sense_r`, `sense_range` flags, save v9; kernel reads v9 and refuses the flag
15. [x] Item 10, commit 3: `sense_r` experiment (on / neutral / off, P1), verdict as fixed in ADR-0014
16. [x] G2 M6 step 1: profile the Rust reference kernel; bit-exact speed-ups only, every golden hash unchanged
17. [x] G2 M6 step 2: ADR-0015, the owner deferred the parallel kernel (reopen only for a concrete need)
18. [?] G3 P1: UI Toolkit shell replaces IMGUI in the Unity viewer (`docs/G3_PLAN.md`); owner checks in Play mode
19. [?] G3 P2: camera (pan, pinch/wheel zoom, x wrap), Input System; PlayMode tests; owner checks with a mouse

## Rules for every piece
- **Verdict** as written in the ADR piece, fixed before the run; a failed verdict is fixed on the Rust side
  (changing Python's maths or `play.py`'s edits is the owner's decision only).
- **Existing sets**: every committed `hashes.csv` stays byte-identical (creation and interventions are off the
  load and step path).
- **Before each push**: `pytest`, `ruff check .`, `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`,
  `cargo test --locked`. Each ABI change bumps `WS_ABI_VERSION` once, with the Unity wrapper (ADR-0012 rule).

## Item 10: evolvable perception radius `sense_r` (owner's proposal, 2026-11-11)
**Problem.** A cell perceives only its 8 neighbours (radius 1). ROADMAP F3 names this as a likely reason no hunting
or fleeing appears and already suggests "a wider perception radius" as the next step. The idea: make the radius an
evolving trait, not a fixed parameter.

**Mechanism.**
- New flag `Config.sense_range` (off by default; acts only with `sensing` on) and a control arm
  `sense_range_neutral`: the trait is inherited, mutates and costs, but the radius stays 1.
- Per-cell trait `sense_r` in [0, 1], handled like `armor_p`: founders and immigrants draw it after `armor_p`;
  children inherit it mutated with `mut_sigma`, never from the partner.
- Effective radius `R = min(sense_radius_max, 1 + int(sense_r * sense_radius_max))`; `sense_radius_max` is an
  integer with a hard bound in `_BOUNDS` (e.g. 1..5), since configs come from untrusted saves.
- Cost per step: `sense_range_upkeep * (R - 1)`, paid in the neutral arm too.
- `sensed_move` generalised: the move stays one tile, only what the cell sees changes. For each candidate tile t:
  environment inputs (light, organic, chemical energy) = mean over tiles within Chebyshev distance `R-1` of t (t
  alone for R = 1, as today); social inputs (kin, strangers, danger) = cells within R of both the mover and t, the
  mover excluded, normalised by the in-grid tiles within R of both. With R == 1 the current code runs, identical
  float for float to F3.

**Constraints found in the code.**
- Not a 17th gene: `random_genes()` would draw 17 values, changing every world's RNG stream, all 18 golden sets and
  the species distance. It is a trait outside the genome, like `sex_p`, `plast_p`, `hgt_p`, `armor_p`.
- ADR-0011 says the fifth trait outside the genome triggers the "extended genome" refactor; `sense_r` is the fifth,
  so decide first: do the refactor, or defer it again with a reasoned ADR-0014.
- Flag off: no new RNG draw, proven by byte-identical `hashes.csv` of `default` and `volcanic`.
- Save v9 (cell row of 16 fields): the Rust kernel must read v9 or neither the kernel nor Unity loads anything
  (`SAVE_VERSION`, `CELL_ROW_LEN`, `config.rs`, the bound checks in `save.rs`, `hash.rs` with the slot hashed only
  when on), then regenerate the golden sets. Advice: the kernel refuses `sense_range=1` until the mechanism is
  validated and its port becomes a later item; this breaks "every flag ported" and must be said explicitly.
- Edges: in narrow worlds the x wrap revisits tiles (use a `seen` set); top and bottom rows need handling, since
  `VIEWS` covers radius 1 only; sums in a fixed order with Python floats, no numpy, so a Rust port stays bit-exact.
- Python files: `config.py`; `world.py` (slot, `express`, seeding, immigration, division, `sensed_move`, `stats`);
  `persistence.py`, `run.py`, `plots.py`, the `view.py` inspector; `scripts/g2_golden.py`; a new
  `tests/test_sense_range.py` modelled on `test_defence.py`.
- Performance: steps/s with the flag off, before and after.

**Experiment (verdict fixed before the runs).** Arms on / neutral / off, `sensing=1`, immigration 0, flat world with
day/night plus `volcanic.json`, P1 standard (30k steps x 20 pairs). Questions: (1) is `sense_r` selected (on vs
neutral, >= 16/20 pairs)? (2) do hunting or fleeing appear (`w_danger`, kills by mobile predators)? Known risk: with
immigration 0 the median life is 6-8 steps and almost no cell moves, so the result may be null for the same reason
as F3 and F5d; also try it where F5e lengthens life (`defence=1`) or on the flat world.

**Results log.**
- **Commit 1, trait table (2026-11-12).** `worldsim/world.py` holds the four traits in `TRAITS`; founders,
  immigrants, children, upkeep, stats, save checks and the inspector loop over it (ADR-0014 decision 1).
  Verdict met:
  - a full `g2_golden.py --all` into a fresh root reproduced every committed `hashes.csv`, render, `config.json`,
    the three vector files and the decompressed start saves byte for byte;
  - pytest 352 passed (99.32%), ruff clean; the four F5 test files changed only for `traits=make_traits(...)` and
    `offspring_traits`, plus the new `tests/test_traits.py`;
  - steps/s with every flag off (CPU time, five interleaved runs each): before 387 / 483 / 471 / 490 / 510, after
    465 / 467 / 506 / 487 / 516, within the machine's noise. A first wall-clock pass read 3-4% slower; the
    interleaved run did not reproduce it.
- **Commit 2, `sense_r` and save v9 (2026-11-12).** `Config.sense_range` / `sense_range_neutral` /
  `sense_radius_max` (3, bounded 1..5) / `sense_range_upkeep` (0.05); `sense_r` is the table's fifth trait;
  `World.sensed_move_wide` handles R > 1 and F3's code still runs at R = 1. Deviations from the ADR text, decided
  while implementing:
  - the table entry has upkeep `None`: the cost is `sense_range_upkeep x (R - 1)` from the *genetic* radius,
    added in `express()` after the table loop (a linear table upkeep would have charged twice). The neutral arm
    pays it and senses at radius 1;
  - `Config.validate` refuses `sense_range` without `sensing` (the trait would cost and do nothing) and with
    `width < 2 x sense_radius_max + 1`, so no tile is seen twice across the x wrap. This replaces the `seen` set:
    the windows and the view counts need no dedupe, and the normalisation has a closed form;
  - environment inputs are means of the per-tile F3 inputs (`light / light_max`, `o / (o + 1)`, `ch / (ch + 1)`)
    over the window. At R = 1 the general function makes the same choices with the same draws as F3's code
    (pytest, 6 seeds with rock, vents and edge rows); its scores may differ in the last bit (product order), which
    is why R = 1 keeps F3's code.

  Verdict:
  - every committed `hashes.csv` and render is byte-identical after a full `--all` into a fresh root. Only the
    start saves (v9: `sense_r` as the 16th field, 0.0), `rng.json` (`save_version` 9), `create.json` and the two
    creation `config.json` files changed, and only by the four new config keys and the version (checked by
    decoding them);
  - the kernel reads v9 and refuses `sense_range` on (in `Config::check_relations`, so saves and
    `ws_world_create` alike) and a non-zero `sense_r`; `cargo test`, `fmt` and `clippy` pass;
  - pytest 366 passed (99.36%), with the new `tests/test_sense_range.py`;
  - steps/s, CPU time, interleaved: flags off before 646 / 646 / 640 / 646, after 653 / 634 / 627 / 667 (noise);
    `sensing=1` before 441 / 432 / 427 / 435 / 430 / 444, after 424 / 427 / 372 / 441 / 424 / 432 (median about
    2% lower, ranges overlap); `sense_range` on, about 720 cells, `sense_radius_max` 3: 368-421, 5: 512-516.
  - security review: no blockers (its fuzz against a naive tile-enumerating reference matched 14,470 moves, R 2-5,
    heights 2-12, minimal widths); its nits applied (docstrings, a draw-counting test, a v8-row test in Rust, the
    upkeep deviation noted in `docs/ARCHITECTURE.md`).

## Item 15: `sense_r` experiment (rules fixed 2026-11-12, before any run)
`python scripts/sense_range_experiment.py --steps 30000` and the same with `--defence` (F5e armour on in every arm,
longer lives; ADR-0014: part of the plan, not a rescue). Arms, all with `sensing=1` and immigration 0: off, on,
neutral, control (neutral with `sense_range_upkeep` 0.5). P1 standard: 30k steps, second half, descendants only,
flat world with day/night + seasons and `volcanic.json`, seeds 1 3 ... 19 = 20 pairs.
1. Positive control: `sense_r` control < neutral in >= 16/20, else rule 2 is not claimed.
2. Selection: `sense_r` on > neutral in >= 16/20 -> selected; on < neutral in >= 16/20 -> selected against.
3. Behaviour, on vs neutral at >= 16/20: fleeing = mean `w_danger` of descendants lower; hunting = share of
   predation attempts by mobile unbonded predators (`move` > 0.3) higher. On vs off reported too.
4. Exactly 16/20 is "at the threshold, not confirmed on new seeds". A null result is reported as null.

**Result (2026-11-12): null.** Script `scripts/sense_range_experiment.py`; data in `docs/sense_range_experiment.csv`
and `docs/sense_range_defence.csv`; the full table is in ROADMAP F3.
- The positive control fires: 16/20, at the threshold, in the base run; 19/20 with armour.
- Selection on vs neutral: 11/20 and 8/20, so no detectable selection.
- Fleeing (9/20, 10/20) and hunting (11/20, 10/20): no consistent sign.

Consequences:
- `sense_range` stays Python-only, and the kernel keeps refusing it (ADR-0014).
- The science half of item 11 loses its premise. It said "only makes sense if item 10 shows that a wider perception
  radius is selected". Item 11 is to be rescoped by the owner: game-only, or with a new hypothesis.

## Item 11: obstacles and scattered resources that make exploration pay (owner's idea, 2026-11-11)
**Parked (owner, 2026-11-12).** Item 10 gave a null result, so this mechanism is kept aside as a hypothesis
to revisit when movement matters more in the world; no engine work until then.

**Idea.** Use the terrain together with `sense_r` (item 10): obstacles placed at random by the world generator, or
by the player as a game move, so that resources sit behind or between them and cells must explore to find them.
The starting point, how energy disperses and how resources are resupplied become game variables too.

**What already exists.** The player can already place obstacles: `play.py` has `raise_rock` and `dig` (G1, and the
kernel port of ADR-0013), plus `add_vent` and `add_nutrients` for resources. Procedural rock is only a seabed
ridge (`seabed_heights`), so a generated world has no free-standing obstacles yet.

**Open points (to scope after item 10 has a result).**
- Engine: a generator of scattered rock (islands, walls, caves) and of patchy resources (vents and organic in
  clusters, resupplied over time); each a `Config` field, off by default, with its own terrain RNG draws only when
  on (existing worlds and golden sets unchanged); stored in saves like every terrain map (ADR-0004).
- Game: start position, energy dispersion (organic diffusion and decay) and resupply rate as parameters of a
  scenario or a difficulty level, not new engine rules where `Config` already has them.
- Science: it only makes sense if item 10 shows that a wider perception radius is selected; the experiment is the
  same arms (on / neutral / off) on a patchy world against a uniform one, asking whether `sense_r` rises more where
  resources are scattered. Verdict to be fixed before the runs.
