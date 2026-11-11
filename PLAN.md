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
9. [?] ADR-0013 piece 5: Unity sandbox tools from exported `GameRules()` parameters (checked by hand)
10. [ ] Owner's idea (2026-11-11, as soon as possible): evolvable perception radius `sense_r` (see below)
11. [ ] Owner's idea (2026-11-11, after 10): obstacles and scattered resources that make exploration pay (see below)

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

## Item 11: obstacles and scattered resources that make exploration pay (owner's idea, 2026-11-11)
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
