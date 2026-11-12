# Developer Guide

Last updated: 2026-11-10

**`./scripts/bootstrap-dev.ps1` (Windows) or `./scripts/bootstrap-dev.sh` — run once per clone.**

## What the bootstrap does
1. `git config core.hooksPath .githooks` — enables the committed hooks:
   `pre-commit` (secret scan) and `post-commit` (background knowledge-graph refresh).
   Git hooks do not survive a clone; this line is what makes them real.
2. `pip install -r requirements.txt -r requirements-dev.txt`.
3. `pre-commit install` if the `pre-commit` framework is available (gitleaks,
   ruff, whitespace checks); otherwise the hook's inline fallback scan runs.
4. Builds the Graphify knowledge graph if `graphify-out/graph.json` is missing
   (`--code-only` unless an LLM API key is set).

## One-off machine installs
- Python 3.12+.
- `pip install pre-commit` — full secret scanning and linting on commit.
- `uv tool install graphifyy` then `graphify install` — knowledge graph used by
  AI agents to orient cheaply in the codebase (optional; agents fall back to search).

## Secrets
WorldSim needs none today. If a key is ever needed, add it empty to
`.env.example` and put the real value in `.env` (git-ignored).

## Running
```bash
python game.py                                                 # play the G1 prototype
python view.py                                                 # interactive viewer
python run.py --steps 10000 --seed 1 --out runs/test1          # headless run
python run.py --steps 5000 --out runs/test2 --set pred_eff=0.7 # override any Config field
python run.py --steps 5000 --seed 1 --out runs/a --save-every 1000         # periodic saves
python run.py --resume runs/a/world_003000.json.gz --steps 2000 --out runs/b  # continue a save
python view.py --load runs/a/world_final.json.gz                           # open a save
python run.py --planet examples/volcanic.json --steps 5000 --out runs/v   # planet from a form
python view.py --planet examples/planet.png                               # planet from an image
python view.py --set rock_fraction=0.3 --set day_amplitude=1              # viewer overrides
```
A run writes `config.json`, `stats.csv`, `snap_*.png`, `world_final.json.gz`
(+ `world_NNNNNN.json.gz`), `stats.png`, and with species tracking (default;
`--no-species` to disable) `species.csv`, `species_tree.png`, `novelty.png`.
Species parameters (`species_threshold`, `novelty_activity`, `species_prune_peak`)
only change the analysis, never the simulation. Every `Config` is range-checked
(`Config.validate()`); environment fields: `day_length`, `day_amplitude`,
`year_length`, `season_amplitude`, `rock_fraction`, `vent_count`, `vent_strength`,
`vent_radius`, `chemo_gain`. A planet form is JSON with `star` (`red_dwarf`, `sun`,
`blue_giant`), `day_night`, `seasonality`, `ocean_depth`, `seabed_relief`,
`volcanism`, `mineral_richness`, optional `seed`, `name` and `config` overrides —
see `examples/`.
Viewer keys: `SPACE` pause · `N` one step · `+/-` speed · `O` organic matter ·
`S` snapshot · `R` new world · click = inspect a cell.

## Tests and lint
```bash
pytest                                   # full suite, coverage gate from pyproject.toml
pytest tests/test_world.py::test_name    # single test
ruff check .                             # lint

# Rust core (G2, engine-rs/): needs a stable Rust toolchain
cd engine-rs && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test

# regenerate every G2 golden set after any change to the dynamics (the sets are listed in SETS
# in scripts/g2_golden.py; a new set also goes into GOLDEN_SETS in engine-rs/tests/common/mod.rs)
python scripts/g2_golden.py --all engine-rs/tests/golden
# (also writes engine-rs/tests/golden/terrain.json, create.json and interventions.json, the procedural-terrain,
#  world-creation and interventions vectors; alone: python scripts/g2_terrain_vectors.py --out
#  engine-rs/tests/golden/terrain.json, python scripts/g2_create_vectors.py --out engine-rs/tests/golden/create.json
#  and python scripts/g2_intervention_vectors.py --root engine-rs/tests/golden
#  --out engine-rs/tests/golden/interventions.json, which reads the sets' start saves)
# numpy mean vectors (ndarray.mean(), pairwise summation; tied to the installed numpy)
python scripts/g2_mean_vectors.py --out engine-rs/tests/mean_vectors.json
# seeding vectors (random.Random(seed) for int and str seeds; platform-independent)
python scripts/g2_seed_vectors.py --out engine-rs/tests/seed_vectors.json
# genome distance vectors (math.dist is CPython's own algorithm; platform-independent)
python scripts/g2_distance_vectors.py --out engine-rs/tests/genome_distance.json
# one-off world with overrides, e.g. to try a flag before it becomes a set
python scripts/g2_golden.py --planet examples/volcanic.json --set defence=1 --out engine-rs/target/try
# after a change to render.py only: rewrite the two golden renders of a set, nothing else
python scripts/g2_golden.py --renders-only --steps 1000 --out engine-rs/tests/golden/default

# C ABI for front-ends (Unity): engine-rs/target/release/worldsim_core.dll (src/ffi.rs documents the contract)
cd engine-rs && cargo build --release
```

### Unity front-end (G2 M4, `unity/`)
Unity 6 (6000.5.6f1) project that loads a save into the Rust kernel through P/Invoke and shows it.
Not in CI (Unity needs a licence): run its tests locally after a change to `ffi.rs` or `unity/`.
```bash
# build the kernel and copy the DLL + a save into the project (both git-ignored)
python scripts/unity_sync.py                                  # default golden start save (-> StreamingAssets/world.save)
python scripts/unity_sync.py --save runs/a/world_final.json.gz  # or any v9 save, default flags
python scripts/unity_sync.py --planet examples/red_dwarf.json   # config for New world (default: volcanic)
# regenerate the scene from code (Assets/Scenes/WorldSim.unity)
Unity -batchmode -quit -projectPath unity -executeMethod WorldSim.EditorTools.WorldSimSetup.CreateScene
# EditMode tests: golden hashes and renders through P/Invoke
Unity -batchmode -projectPath unity -runTests -testPlatform EditMode -testResults unity-tests.xml
# PlayMode tests (G3 P2): without -batchmode, so the Editor has a window and the UI gets input
Unity -projectPath unity -runTests -testPlatform PlayMode -testResults unity-play.xml
# Android (G3 P3): once, rustup target add aarch64-linux-android; the Editor needs its Android module
python scripts/unity_sync.py --android      # + libworldsim_core.so for arm64, linked by the Editor's own NDK
Unity -batchmode -quit -projectPath unity -buildTarget Android -executeMethod WorldSim.EditorTools.WorldSimSetup.BuildAndroid
python scripts/android_check.py             # device check APK: golden sets and kernel speed on a phone over adb
```
- The editor locks a loaded native library: close it before re-running `unity_sync.py` after a
  kernel change (the script says so when the copy fails).
- **Render pipeline: URP 17.5** (the Built-in pipeline is deprecated in Unity 6). `Assets/Settings/WorldSim_URP.asset`
  (+ `_Renderer`, no post-processing, MSAA off) is assigned in Graphics and in every Quality level;
  `WorldSimSetup.ConfigureRenderPipeline` (menu *WorldSim > Configure render pipeline*) recreates and reassigns it.
  The scene camera only clears to black and carries `UniversalAdditionalCameraData` (post-processing off); the world
  is a UI Toolkit panel on top. The project has no materials, lights or custom shaders, so nothing else depends on
  the pipeline. Packages are kept minimal: URP, Test Framework, Input System 1.20 (bundled with the Editor), UI
  Toolkit (the viewer), the IMGUI, JSON and UnityWebRequest modules; URP pulls in its own dependencies.
- **UI (G3 P1)**: UI Toolkit. `Assets/WorldSim/UI/WorldSimView.uxml` is the layout (HUD, control bar, world, tool
  dock), `WorldSimView.uss` the Neon Abyss style, `WorldSimTheme.tss` the theme and `WorldSimPanel.asset` the panel
  settings (scale with screen size from 1280x720, created by `CreateScene`). The world is shown through a
  `WorldCamera` (G3 P2): a whole number of device pixels per tile, from "the whole depth fits" (the first view) up to
  `maxScale`; x wraps, y is clamped. The point-filtered texture is drawn as side-by-side `Image` copies in a clipped
  `#world`, so the seam needs no texture repeat. The root gets `ws-portrait` or
  `ws-landscape` and padding from `Screen.safeArea`. Font: Pixelify Sans (`UI/Fonts`, SIL OFL, `OFL.txt` beside
  it). **Input: the Input System package only** (`activeInputHandler: 1`); UI Toolkit reads it through the package's
  `InputSystemProvider`, so the scene needs no EventSystem. On the world: drag pans, pinch (two fingers) or the
  wheel zooms about the fingers or the cursor, and a tap (a press that moves less than `tapSlop` and is never joined
  by a second finger) applies the selected tool or, with none, names the tile in the dock. Keys (Space, N, +/-) come
  from `Keyboard.current` (none on a phone) and are ignored while the seed field has the focus.
- **Android (G3 P3)**: IL2CPP, ARM64 only, min API 26, provisional id `com.kydodev.worldsim` (the device check is
  `com.kydodev.worldsim.check`); APKs go to `unity/Builds/Android/`. The two kernel libraries sit in the git-ignored
  Plugins folder, so `WorldSimSetup.ConfigureAndroid` sets their import settings from code (.so: Android ARM64; .dll:
  Editor and Windows). On Android StreamingAssets stay inside the APK: `StreamingRead` reads them through
  `UnityWebRequest` (the desktop reads the file directly), and the build gunzips any `*.gz` there, so the bundled save
  is `world.save` (gzip inside). The golden sets differ on ARM (G3_PLAN P3), so `android_check.py` reports
  "equal" or "not-comparable" with the first diverging step. MIUI phones refuse `adb install` unless "Install via
  USB" is on; otherwise copy the APK to the phone (`adb push ... /sdcard/Download/`) and install it by hand. A build
  with `-buildTarget Android` leaves the project on Android: pass `-buildTarget StandaloneWindows64` to the next run.
- **Batchmode gives the UI no input**: with no window, UI Toolkit drops runtime input (the device gets its events,
  the panel none), so `VirtualInputReachesTheView` skips itself in batchmode; run PlayMode without `-batchmode`.
- Code: `Assets/WorldSim/Runtime/NativeWorld.cs` (wrapper; `AbiVersion` must match `ws_abi_version`),
  `WorldSimView.cs` (texture, controls), `StreamingRead.cs` (StreamingAssets on desktop and Android), `DeviceCheck.cs` (P3 device check), `WorldCamera.cs` (zoom, pan, screen point to tile), `Editor/DropInternetPermission.cs` (no `INTERNET` in the APK manifest), `Editor/WorldSimSetup.cs` (scene,
  panel, URP settings), `Tests/Editor/` (EditMode), `Tests/Play/` (PlayMode).
- **New world** (ADR-0012): the kernel creates a world from `StreamingAssets/world_config.json` (a planet
  form's config, exported by `unity_sync.py`) and the seed typed in the bar (Return or the button). Planet forms
  and images themselves stay in Python; a kernel-made world cannot be saved yet.
- **Edits** (ADR-0013): `NativeWorld.Intervene(Edit, x, y, radius, amount)` applies a G1 tool between steps,
  bit-exact with `worldsim/play.py`; a refusal throws `WorldSimException` with `Status == StatusInvalid` and leaves
  the world as it was. In the viewer, the dock under the world picks a tool (tap it again to put it down) and a
  left click or tap on the world applies it; the parameters come from `StreamingAssets/game_tools.json`, which
  `unity_sync.py` exports from `GameRules()`. A sandbox: no budget or milestones until G3.
See [TEST_STRATEGY.md](TEST_STRATEGY.md). Record results in `TEST.md` (archive
the previous content into `test_history.md` first).

## Experiments
A new mechanism lands with an experiment: the `run.py` command, the seed(s),
and the outcome, recorded in the relevant design doc or ROADMAP phase. Compare
the same seed before and after a change.

## Standards and conventions
[`CLAUDE.md`](../CLAUDE.md) is the authority. In short: English for all new
code/docs, every tunable in `Config`, all randomness through `World.rng`,
Conventional Commits (`feat(engine): ...`), small commits straight to `main`
(no feature branches or PRs; run the CI checks locally before pushing; the GitHub
ruleset forbids force-push and deleting `main`).

Target: a new contributor goes from clone to a running viewer in under 30
minutes following only this document.
