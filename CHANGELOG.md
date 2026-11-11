# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); commits follow Conventional Commits.

## [Unreleased]

### Added
- **G2 M5, `sex` in the Rust kernel**: saves with F5a two-parent division load and run in the kernel, equal to
  Python at every step of new golden sets `sex` (2631 sexual births in 1000 steps) and `sex_neutral`. Mate choice
  uses CPython's own `math.dist` algorithm, reproduced in Rust and checked bit for bit on 700 gene pairs, subnormal ones included
  (`scripts/g2_distance_vectors.py`). Earlier hashes unchanged; speed within noise.
- **G2 M5, `plasticity` in the Rust kernel**: saves with F5b diet acclimation load and run in the kernel, equal to
  Python at every step and in the renders of new golden sets `plasticity` (538 of 555 cells acclimated) and
  `plastic_neutral`; the kernel's render now colours cells by their (acclimated) feeding shares. The state hash
  covers `plast_p` and the diet when the flag is on (earlier hashes unchanged). Speed within a few percent.
- **G2 M5, `hgt` in the Rust kernel**: saves with F5c gene transfer load and run in the kernel, equal to Python at
  every step of new golden sets `hgt` (26594 genes copied in 1000 steps) and `hgt_neutral`; the state hash covers
  `hgt_p` and the transfer counters when the flag is on (earlier hashes unchanged). No speed change.
- **G2 M5, `defence` in the Rust kernel**: saves with F5e prey defence now load and run in the kernel, equal to
  Python at every step of new golden sets `defence` (13002 attacks repelled in its 1000 steps) and `defence_neutral`; the state hash
  covers `armor_p` and `defended` when the flag is on, so the existing hashes are unchanged. `rng.json` meta
  records the counter deltas of the hashed steps. No speed change.
- **G2 M5 started**: `scripts/g2_golden.py` takes `--set KEY=VALUE` and `--all ROOT`, with the golden sets listed
  once (`SETS`), so each optional flag can get its own golden set; pytest checks the lists agree and CI regenerates
  every set with `--all`. Plan in `PLAN.md` (one flag at a time, verdict rules fixed before any run).
- **G2 M4 part B, Unity front-end** (`unity/`, Unity 6000.5.6f1): loads a save into the Rust kernel through
  P/Invoke and shows it as a texture with play/pause, step and speed. `scripts/unity_sync.py` builds the kernel
  and copies the DLL and a save into the project (git-ignored). EditMode tests check golden hashes and renders
  through P/Invoke. Viewer only; not in CI (Unity needs a licence).
- **G2 M4 part A, C ABI**: `engine-rs` exports a C interface for front-ends (`ws_world_load` from save bytes,
  `ws_world_step`, `ws_world_info`, `ws_world_state_hash`, `ws_world_render_rgb`, `ws_last_error`,
  `ws_abi_version`), panic-safe and checked on every pointer and buffer. The kernel renders the world like
  `render.py`, byte for byte (new golden renders), and computes the light at load like Python.
- **F5e Prey defence** (ADR-0011): `--set defence=1` gives cells an evolvable armour `armor_p`; an attack
  fails with chance `armor_p` x `defence_strength` (0.8, capped at 0.95), at a cost of `defence_upkeep` (0.2)
  x `armor_p` per step; neutral arm `defence_neutral`. Save format v8 (`armor_p` per cell, counter `defended`;
  Rust loader reads v8 and refuses `defence` until M5, golden saves regenerated, hashes unchanged); stats
  `armor_p_mean`/`defended`; `armor` in the viewer inspector. Experiment `scripts/f5e_experiment.py` (P1
  standard): armour beneficial (20/20) and selected (19/20), lives about 4x longer (median 28 vs 7.5 steps,
  20/20), but the pre-registered long-life-world criterion fails at 15/20 (short lives on volcanic runs with
  many predators).
- **World study** (`scripts/world_study.py`, criteria pre-registered): lives are short because predation is diffuse
  (most kills by mostly photo/chemo cells). No predation, cost or specialisation setting gives a stable long-life
  world: the best 10k-step setting failed the 30k check on 20 pairs (7/20). A pilot of memory regulators (not
  committed) was nearly inert for the same reason. The default world is unchanged.
- **F3 re-run at the P1 standard** (`scripts/f3_p1_experiment.py`, rules pre-registered and committed before
  each run): positive control fires (16/20, then 19/20); phototaxis with cost-free sensing vs off 13/20 then
  16/20 (at the threshold): a lean towards light, not established; flat planet 9/10 twice. Almost no cell moves
  with immigration 0 (median 1–3 motile cells), so sensing has little to act on.
- **F5d learning probe**: learning on the F3 sensor weights would be inert in this world (median life 6–8
  steps, 0.4–2.5 sensed moves per life); not built, recorded in ROADMAP.
- **G2 milestone M3**: benchmark of the Rust reference kernel (`scripts/g2_bench.py`,
  `cargo run --release --example bench`): single-threaded 5–8×10⁶ cell-updates/s, ~48k cells at
  ~110 steps/s, about 3× the 60 fps target and 12–27× Python on the same worlds; the kernel's
  hash still equals Python's on the 10k and 50k worlds.
- **G2 milestone M2**: the Rust kernel ports `World.step()` for the default flags
  (terrain, vents, day/night and seasons included) and reproduces Python's state hash at
  every one of 1000 steps on both golden sets, bit-for-bit (Windows). On a mismatch the
  test names the first divergent step and, with `scripts/g2_golden.py --dump-step N`, the
  first differing field.
- **F5c Horizontal gene transfer** (third F5 mechanism, ADR-0010): `--set hgt=1` gives cells an
  evolvable propensity `hgt_p` to copy one fixed gene from a random neighbour during life (cost
  `hgt_upkeep` x `hgt_p`); neutral arm `hgt_neutral`; save format v7 (`hgt_p` per cell, counters
  `hgt_events`/`hgt_foreign`; G2 golden sets regenerated, hashes unchanged, Rust `SAVE_VERSION` 7);
  stats `hgt_p_mean`/`hgt_events`/`hgt_foreign`; `hgt` in the viewer inspector. Experiment
  `scripts/f5c_experiment.py` (P1 standard + confirmation on seeds 21–39): transfer itself has no
  detectable effect (donors are near-clones: the mechanism is nearly inert here); net selection is
  against it through its cost (16/20, then 18/20 on new seeds). Species counts rise because of the
  transfer, cause untested (16/20 twice); diversity falls, consistent with the cost but not
  established. The review's notes
  added a loader check (`hgt_foreign` <= `hgt_events`) and the 16/20 threshold caveat.
- **F5b confirmation** on seeds 21–39 (`docs/f5b_confirm.csv`): population on > off 16/20 again.
- **G2 milestone M1c**: the Rust kernel (`engine-rs/`) loads a v6 save (gzip JSON, validated
  like `persistence.py`: untrusted input returns errors, never panics; unknown config keys
  are refused; typed, length-capped parsing keeps memory proportional to the data) and
  computes the G2 state hash; it equals Python's step-0 hash on both golden sets. New crate
  dependencies: `flate2`, `serde`, `serde_json`, `sha2`. A new `Config` field must now
  also be declared in `engine-rs/src/config.rs` (see `docs/G2_PLAN.md`).
- **F5b Diet plasticity** (second F5 mechanism, ADR-0009): `--set plasticity=1` gives
  cells an evolvable acclimation rate; during life the photo/sapro/chemo split shifts
  towards the food on the tile (lagged, with a per-step cost); neutral arm
  `plastic_neutral`; save format v6; `plast_p_mean`/`diet_shift` stats; plasticity in the
  viewer inspector. Experiment `scripts/f5b_experiment.py` (P1 standard): against a
  cost-matched control, acclimation is favoured (19/20 pairs); its net selection against a
  free neutral arm is not detectable (14/20): benefit and cost are about equal. Population
  higher in 16/20. A review fix (cells without feeding genes were fed as generalists under
  plasticity) came before the final run.
  G2 golden vectors regenerated for save v6 (state hashes unchanged: the default world
  is identical) and the Rust kernel's `SAVE_VERSION` set to 6.
- **P1 experiment power**: `--immigration` option in `scripts/f4_experiment.py` and
  `scripts/f5_experiment.py`; the F5 verdict covers every sexual arm present. A positive
  control (`sex_cost=4`) is detected at 30k steps (16/20 pairs, with or without
  immigration); re-asked there, sex at cost 0 shows no detectable selection (8/20, 9/20).
  New methods standard in ROADMAP.
- **G2 engine port, design step**: ADR-0008 compares Unity + C# with a Rust core on
  determinism, verifiability against Python, performance and maintenance; the owner
  chose a Rust core (`engine-rs/`) called from Unity, in this repository. Milestone
  plan in `docs/G2_PLAN.md`.
- **G2 milestones M0–M1a**: `scripts/g2_golden.py` writes golden vectors (a v5 save,
  CPython RNG draws, per-step state hashes; flat default world and `volcanic.json`) to
  `engine-rs/tests/golden/`, checked by
  `tests/test_g2_golden.py`; Rust crate skeleton `worldsim-core` in `engine-rs/` with a
  `rust-core` CI job (fmt, clippy, test).
- **G2 milestone M1b**: `worldsim_core::rng::PyRandom`, CPython 3.12's `random.Random`
  in Rust (MT19937 restored from `getstate()`, `random`, `getrandbits`, `randrange`, `choice`,
  `shuffle`, `gauss` with its `gauss_next` cache); `engine-rs/tests/golden_rng.rs` matches every
  golden draw and the end state bit-for-bit on Windows. `serde_json` added as a dev-dependency.
- **G2 golden sets per platform**: the committed golden sets are the Windows reference; the
  `rust-core` CI job regenerates them on Linux and tests against those (`WORLDSIM_GOLDEN_DIR`),
  after Linux showed 25/750 `gauss` draws 1 ULP off the Windows-made set. Still bit-exact.
- **F5a Two parents** (first of the four F5 mechanisms, ADR-0007): `--set sex=1` gives
  cells an evolvable mating propensity; at division they may recombine (uniform
  crossover) with a genetically close cell within `mate_radius`, at `sex_cost`; neutral
  arm `sex_neutral`; save format v5; `sex_births`/`sex_p_mean` stats; propensity in the
  viewer inspector. Experiment `scripts/f5_experiment.py`: no detectable selection on
  the propensity and no confirmed consequence — inconclusive, since a positive control
  (a large mating cost) was not detected either.
- **F4 Open genome** (roadmap phase complete, ADR-0006): variable-length rule genes
  (condition on own energy or light → sensor weight or division threshold) with
  duplication, deletion, de novo insertion and a per-rule cost, `--set open_genome=1`;
  neutral control arm `rules_neutral`; save format v4; `rules_mean`/`rules_max` stats;
  rules in the viewer inspector. Experiment `scripts/f4_experiment.py`: pre-registered
  verdict null overall; rules earn their keep on the volcanic planet (confirmed on new
  seeds, mechanism unknown), no effect seen on the flat one (5 seeds); no single rule
  type selected; novelty unchanged.
- **F3 Sensors and behavior** (roadmap phase complete, ADR-0005): six sensor genes
  (`w_light`, `w_organic`, `w_chem`, `w_kin`, `w_stranger`, `w_danger`) and directed
  movement with `--set sensing=1` (`sense_noise`, `sense_upkeep`); off by default.
  Species distance rescaled per gene; save format v3. Experiment script
  `scripts/f3_experiment.py` and results (phototaxis likely selected, modest effect on 2 seeds; no fleeing,
  hunting or consistent day/night migration). Viewer inspector shows sensor weights.

### Fixed
- **No numpy transcendentals left in terrain generation or interventions** (G2, before M5): the
  vent field (generation and the G1 vent tool, now one helper `terrain.vent_plume`) uses
  `math.exp` and an exact `sqrt` of the integer distance; `seabed_heights` uses `math.sin`; the
  image-planet gradient uses `sqrt(gx*gx + gy*gy)` (not `math.hypot`, which is not libm).
  Windows results are bit-identical (both golden sets regenerated, unchanged; only Windows was
  measured). On AVX-512 CPUs vent/relief planets may differ by an ULP from before, and on any
  non-Windows platform photo planets may gain or lose rock at the edge threshold (glibc `hypot`
  vs the sqrt form, not compared). Generating vents
  on very large worlds is slower (~0.75 s per vent at the 1M-tile cap).
- **CI**: the `rust-core` job builds and tests with `--locked` and audits the crate's
  dependencies against RustSec (`cargo deny check advisories`, prebuilt binary, action pinned
  by commit SHA).
- **G2 Rust kernel diverged from Python on Linux** (AVX-512 CPUs): numpy's `exp`/`power` SIMD
  paths are not correctly rounded, so the light differed by an ULP at some rows. The light's
  transcendentals now come from libm (`math.exp`, `math.pow`, tabulated per row/count), as in
  the Rust kernel. Windows results are bit-identical (golden hashes unchanged); Linux runs on
  AVX-512 CPUs from before this fix are not reproducible bit-for-bit.
- **G2 Rust loader reads save v7** (main was red after #15 and #14 merged in that order). The M1c loader
  was written for v6. It now knows the four `hgt*` config keys and reads 14-field cell rows. It refuses
  `hgt` (unsupported until M5) and a nonzero `hgt_p` with the flag off. It checks the `hgt_events` and
  `hgt_foreign` counters as Python does. The golden sets on main were already v7, and their hashes are
  unchanged.
- F5a review, before release: the child inherited the partner's mating propensity half
  the time, a transmission bias that faked selection against sex (first experiment run
  discarded); an unaffordable `sex_cost` could drive energy negative; partner search
  counted tiles twice on very narrow worlds. Experiment scripts now run without
  installing the package.
- Save loading: malformed rows, huge JSON numbers and other bad content now raise
  `SaveFormatError` instead of crashing with an unrelated exception (F4 security review).
- G1 *Full ecosystem* milestone fired for an idle player on `volcanic.json` once F3
  changed the random stream (natural vents supplied the chemosynthesizers). Only
  chemosynthesizers around vents the player opened count now.
- Code review of F3: social densities were understated on the surface and floor rows
  (divided by 8 neighbour tiles where only 5 exist); danger ignored predators of the
  mover's own lineage, although predation eats kin; a save whose species tracker did
  not match its cells loaded and then crashed at the first birth — now rejected.
- Test `test_total_extinction_is_not_survival` depended on no immigrant landing in the
  emptied world; it now runs without immigration.
- **G1 "Planet in a jar" prototype** (owner playtest passed 2026-11-10): `game.py` front-end and
  `worldsim/play.py` rules — divine-energy budget, tools (nutrients, meteorite,
  mountain, dig, volcano), five milestones calibrated against idle and scripted
  players, replayable action log. `docs/USER_MANUAL.md`. `view.py` exposes
  `add_world_args`/`create_world` for reuse.
- **F2 Living environment + world seed** (roadmap phase complete, ADR-0004):
  - Light cycles: `day_length`, `day_amplitude`, `year_length`, `season_amplitude`
    (mean-preserving; `World.light_factor(t)`, `light_factor` stats column, viewer line).
  - Terrain (`worldsim/terrain.py`): rocky seabed (`rock_fraction`), hydrothermal vents
    (`vent_count`, `vent_strength`, `vent_radius`), per-column sunlight; own seed-derived RNG.
  - 10th gene `chemo` (chemosynthesis, `chemo_gain`), a fourth feeding strategy:
    cyan in renders and charts, `chemo` stats column.
  - World seed (`worldsim/worldgen.py`): `run.py/view.py --planet` from a JSON form or an
    image; `examples/` with two forms and a sample image.
  - `Config.validate()`: type and range checks for every parameter.
  - Viewer: `--set KEY=VALUE` (shared `Config.apply_overrides`, also used by `run.py`),
    `--seed` with `--planet`, colour legend and strategy swatches in the panel.
  - Tests: `tests/test_environment.py`, `tests/test_worldgen.py`, hardening tests.
  - Experiments and figures in ROADMAP (variable light, vents, planet from an image).
- **F1 Foundations** (roadmap phase complete):
  - Save/load (`worldsim/persistence.py`, ADR-0002): versioned gzip JSON,
    validated on load, bit-exact resume. `run.py --save-every`, `--resume`,
    always a `world_final.json.gz`; `view.py --load`.
  - Species tracking (`worldsim/species.py`, ADR-0003): threshold speciation,
    species tree with pruning, simplified evolutionary activity and novelty.
    `species.csv`, `species_tree.png`, `novelty.png`; new `stats.csv` columns
    `species`, `speciations`, `novelty`, `mean_species_activity`; viewer shows
    the species count. Config: `species_threshold`, `novelty_activity`,
    `species_prune_peak`.
  - `plots.py` (charts moved out of `run.py`); `run.py` reports steps/s.
  - Profiling results in ARCHITECTURE; tests for persistence and species.
- Energy-conservation test on a closed system; grid consistency now checked
  after every step.
- Project governance (init-skia-project v1.5.0): `CLAUDE.md`, `.agents/AGENTS.md`,
  Claude subagents in `.claude/agents/` (senior-architect, code-review-security,
  qa-specialist, doc-keeper, product-manager, simulation-dev).
- Repository safety: `.gitattributes`, extended `.gitignore`, committed
  `.githooks/` (secret-scan pre-commit, graph-refresh post-commit),
  `.pre-commit-config.yaml`, `.env.example`, `scripts/bootstrap-dev.ps1`/`.sh`.
- CI (`.github/workflows/ci.yml`: gitleaks, ruff, pytest with coverage gate,
  headless smoke run) and Dependabot.
- pytest suite of engine invariants (`tests/test_world.py`), `pyproject.toml`
  (pytest, coverage, ruff), `requirements-dev.txt`.
- Docs: `INDEX`, `ARCHITECTURE`, `DEVELOPER_GUIDE`, `TEST_STRATEGY`,
  `DEPLOYMENT_GUIDE`, ADR-0001; `TEST.md`, `test_history.md`.
- Graphify knowledge graph setup (`.graphifyignore`; output git-ignored).

### Changed
- Workflow: work directly on `main`, no feature branches or PRs (owner's rule 2026-11-11); CI checks run
  locally before each push.
- `docs/G2_PLAN.md`: M1c and the golden data no longer name a fixed save version (current
  `SAVE_VERSION`); M5 lists F5b `plasticity` and later flagged F-phases; new section on running
  G2 in parallel with the F-phases (flagged features only, default dynamics frozen while M2
  is open, save bumps regenerate the golden sets).
- Save format v2: stores terrain maps; v1 saves are rejected. Same seed gives a different
  history than F1 (one more gene per genome).
- `view.py`: `R` restarts on the same terrain; window title "WorldSim".
- CI smoke run also generates planets from a form and an image.

### Security
- Planet forms, images and saves are treated as untrusted (review 2026-11-10): bounded
  config values, file-size and decompressed-size caps (gzip bombs), image format whitelist
  (PNG/JPEG/WEBP/BMP/GIF) and pixel cap, counter whitelist, finite/range checks on maps,
  cells and organic matter.
- `Cell.bonds` is an insertion-ordered dict (ordered set) instead of a set, so
  energy-sharing order survives save/load.
- Research and design docs translated to English and renamed
  (`state-of-the-art.md`, `theory.md`, `ROADMAP.md`); README translated.
- ROADMAP: v0 marked done, F1 in progress, per-phase status lines.

- Viewer panel, `run.py` console output and plot labels, CLI help, and all code
  comments/docstrings translated to English.

### Fixed
- CI: `pytest` failed with `ModuleNotFoundError: worldsim` on every run (main and
  all Dependabot PRs) because the `pytest` entry point does not put the repo root
  on `sys.path`; set `pythonpath = ["."]` in `pyproject.toml`.
- Engine: a newborn eaten in its birth step stayed in the cell list as a dead
  ghost for one step (double-counted energy and population, phantom shading).
- Viewer: window height now fits the full cell inspector panel; the last gene
  line (`mut`) was cut off at the default 64-row world size.
- Determinism per seed: `Cell` now hashes by its seed-deterministic `id`, so
  the iteration order of `bonds` sets (colony energy sharing) no longer depends
  on memory addresses. Same seed now gives byte-identical `stats.csv`.
- Removed unused `math` import in `worldsim/world.py`.

## [0.1.0] - 2026-11
- v0: base engine, pygame viewer, headless runner, research/design docs.
