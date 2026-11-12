# G3 — Game front-end plan (Neon Abyss, mobile first)

Goal: turn the Unity viewer (G2 M4) into the game front-end drawn in the **Neon Abyss** design
(moodboard: private Claude Design canvas "WorldSim Moodboard", owner's account). Main targets: phones
and tablets, Android and iOS, portrait and landscape. The engine stays the Rust kernel behind the
C ABI; Python stays the reference lab. This file is the G3 working plan, kept apart from `PLAN.md`
like [G2_PLAN.md](G2_PLAN.md).

## Checklist
1. [x] P0 Owner checks the URP viewer in Play mode (texture visible, row 0 on top, tool click hits the right cell)
2. [?] P1 UI Toolkit shell over today's texture: HUD, tool dock, safe area, Pixelify Sans; IMGUI removed
3. [ ] P2 Touch camera: pinch zoom (integer steps), two-finger pan wrapping in x, tap = inspect cell
4. [ ] P3 Android build spike on ABI 3: arm64 `.so` via cargo-ndk, IL2CPP, golden EditMode set on device
5. [ ] P4 ADR + ABI 4 read-only views (tile snapshot, cell detail, light factor), golden-checked vs Python
6. [ ] P5 Sprite world renderer: data texture + atlas shader, LOD to flat colour, day/night palettes
7. [ ] P6 Inspector bottom sheet and population screen from the ABI 4 views
8. [ ] P7 Game rules in the kernel: budget + 5 milestones (play.py), golden-checked with `play.replay`
9. [ ] P8 Species tracker in the kernel (ADR-0003 observer), species drawer and evolution tree
10. [ ] P9 Tablet landscape layout, sound (ambient + events), polish (idle frames, dying, colony seams)
11. [ ] P10 iOS build (needs a Mac and a static library) — owner's decision, not scheduled

Each phase ends with its verification criterion (below) passing; P1–P3 need no change in `engine-rs/`.
P4 and later touch the kernel and wait until ADR-0014 has landed (the main session owns `engine-rs/` now).

## What the mockups need vs what exists

| Mockup element | Needs | Today |
|---|---|---|
| World, pixel sprites per cell | per tile: occupied, dominant diet, species key, bonded, energy | only `ws_world_render_rgb` (blended colour) |
| Day / night palette | the step's light factor | not exposed (`WsInfo` has size, step, population, births, deaths, kills) |
| HUD population, sparkline | population per step | `WsInfo.population` — enough |
| Population by diet chart | counts per dominant diet | derivable from the tile snapshot (P4) |
| Cell inspector | genes, energy, age, lineage, diet shares, colony size | nothing per cell; **no "generation" field exists** (use age, lineage) |
| Species list, evolution tree | species tracker (ids, parents, birth/extinction) | **no tracker in Rust** (Python only, `species.py`) |
| Milestones, divine-energy budget | `play.py` rules | **Python only**; kernel has the edits (ADR-0013), not the rules |
| Save the game | save from the kernel | **a kernel-made world cannot be saved yet** |
| Tools | `ws_world_intervene` | done (ABI 3) |

Mockup numbers (species names, counts, trends, gene values) are illustrative, not requirements.

## Phases and verification

- **P0** — pass: the owner confirms the four Play-mode checks of the URP migration (`774a4c8`).
- **P1 UI shell** (`unity/` only) — UI Toolkit (UXML + USS) replaces IMGUI; the world stays today's
  point-filtered texture. Layout classes switch on aspect ratio (portrait phone / landscape tablet);
  `Screen.safeArea` padding. Font: Pixelify Sans (SIL OFL, ship `OFL.txt` beside it). Pass: every control
  of today's IMGUI viewer works through the new UI; EditMode tests stay green.
  *Result (2026-11-12)*: built (`WorldSimView.uxml/.uss`, `ViewMath`, panel settings from `CreateScene`);
  EditMode 16/16 with the new `ViewMathTests`. Pending: the owner's Play-mode check of every control.
- **P2 Touch camera** — Input System package (comes back into the manifest). Pinch zoom in integer
  scale steps; pan wraps in x (the world is toroidal), clamps in y; tap maps screen → cell. Pass: a
  PlayMode test maps known screen points to known cells at three zoom levels and across the x seam.
- **P3 Android spike** — `cargo ndk -t arm64-v8a` builds `libworldsim_core.so` into
  `Assets/Plugins/Android/arm64-v8a/`; IL2CPP, ARM64, min API to be set. Check whether the player needs the
  `androidjni` module back. Run the golden checks on a device: ARM's maths library may differ from Windows,
  so per [G2_PLAN.md](G2_PLAN.md) ("Golden sets per platform") the device is compared with Python on a
  matching platform or the check is reported as not comparable — never with a tolerance. Pass: the APK
  starts, loads the bundled save, steps at ≥ 30 steps/s on the default 160×64 world on a mid-range phone.
- **P4 Kernel views (ABI 4, needs an ADR)** — read-only entry points, no RNG, no state change, state hash
  untouched, each wrapped in `catch_unwind` like the others:
  - `ws_world_tiles(handle, out, len)`: one `u32` per tile, packed: kind (empty / photo / chemo / sapro /
    pred, the arg-max of the feeding shares as in `render.rs`), species key (lineage until P8), bonded
    bit, energy quantised to 4 bits, rock/vent bits;
  - `ws_world_cell(handle, x, y, out)`: the inspector record (16 genes, energy, age, lineage, diet
    shares, bond count; colony size computed by the kernel);
  - `WsInfo` gains `light_factor` (the struct size changes, so the ABI number bumps).
  Golden: a Python script exports the same views from the golden saves; Rust and the Unity EditMode tests
  compare byte for byte. Pass: golden equal on Windows and on the Linux CI job.
- **P5 Sprite renderer** — the tile array is uploaded once per frame as a `width × height` data texture;
  one unlit shader draws each tile from a sprite atlas (6 kinds × 2 idle frames, 5×5 px each) and a
  palette LUT (night/day rows, species tints). **Level of detail**: sprites only at ≥ 5 device pixels
  per cell; below that, flat diet colour (today's look). Glow: the URP renderer has no post-processing
  (null `postProcessData`, see DEVELOPER_GUIDE), so the night halo is baked into the atlas (a ring of
  translucent pixels), not bloom. Pass: frame time on the P3 phone ≤ 16 ms at the default world, all
  zoom levels; a screenshot test of a golden save matches a reference image.
- **P6 Inspector and population** — from P4 views. Pass: the inspector's values for a golden cell equal
  the Python export.
- **P7 Game rules** — port `play.py` (budget regeneration, the 5 milestones, their checks) to the
  kernel, RNG-free, plus `ws_game_*` entry points. Pass: `play.replay` of the recorded scripted-player runs
  gives the same milestone steps in Rust; the idle player reaches none (the G1 rule).
- **P8 Species** — port the tracker as a pure observer (it must never touch the RNG; ADR-0003/0005);
  expose a list and parent links. Pass: species ids and parents equal Python's on the golden runs.
- **P9 Tablet, sound, polish** — audio module returns to the manifest; sounds come from snapshot diffs
  (births, deaths, tool use), never from inside the kernel. Pass: owner playtest on a tablet.
- **P10 iOS** — `aarch64-apple-ios` static library, `DllImport("__Internal")` under `UNITY_IOS`, built on
  a Mac. Not scheduled until the owner decides.

## Things the mockups hide
- **World shape**: the default world is 160 × 64 (wide, shallow). A portrait phone at 15 px/cell shows
  26 × 40 cells, so the player pans horizontally a lot and sees the whole depth only zoomed out; the
  first-run zoom should fit the height.
- **Threading**: a handle must not be used by two calls at once. Stepping on a worker thread means that
  thread owns the handle and hands the UI a copied tile snapshot per frame.
- **Packages per phase**: today URP, Test Framework, imgui, jsonserialize, uielements. P2 adds Input
  System; P9 adds audio; P3 may need androidjni.
- **Battery**: cap the frame rate (30 fps when idle), decouple steps from frames.
- **Determinism on device**: the game stays deterministic per platform; cross-platform identical replays
  are not promised (see "Golden sets per platform").

## Decisions that need an ADR (numbers assigned when written)
- ABI 4 read-only views and the tile packing (P4).
- Game rules in the kernel vs in C# (P7). Recommendation: kernel, so replays stay checkable against Python.
- Species tracker in the kernel (P8).

## Owner decisions
1. Android first and iOS later (recommended), or both from the start (needs a Mac).
2. When to port the species tracker: P8 as planned, or earlier with lineage as a stand-in species key.
3. Game rules in Rust (recommended) or C#.

## Design reference (copied from the moodboard)

The full rules (palette roles, pixel icons, base layouts, components, app icon, name candidates) live in
the private Claude Design system "Neon Abyss" (owner's account). The game is called
**Abyss Garden** (owner's choice, 2026-11-12; store and trademark check still to do). *Neon Abyss* is
the art-direction codename only: the name is taken by a 2020 game.

**Sprites**: 5 × 5 px per cell, drawn at an integer scale. `B` base, `H` light, `D` shade, `E` eye
(light colour, white for predators), `.` transparent.

| Kind | Frame 1 | Frame 2 (idle) |
|---|---|---|
| photo | `.BHB. BHBBB BBEBD BBBDD .DDD.` | `.BHB. BBHBB BBEBB DBBBD .DDD.` |
| chemo | `..H.. .HBB. HBEBD .BBD. ..D..` | `..H.. .BHB. HBEBD .DBB. ..D..` |
| sapro | `.BB.. BHBBB BBEB. .BBBD B.DD.` | `..BB. BBHBB .BEBB DBBB. .DD.B` |
| pred | `B.B.B .DBD. BBEBB .DBD. B.B.B` | `.B.B. BDBDB .BEB. BDBDB .B.B.` |
| vent | `..H.. .HBH. .BHB. BBBBB DDDDD` | `...H. .HBH. .BHB. BBBBB DDDDD` |
| organic | one pixel at the centre | one pixel, one row higher |

Dying: colours desaturated to 35 %, every pixel with `(row*3 + col) % 4 == 0` dropped.
Bonded cells: the shared edge gets a column of light (`H`) pixels.

**Neon palette** (night / day), colours as base · light · shade:

| Role | Night | Day |
|---|---|---|
| water top → bottom (7 bands) | `#0d2142` → `#020308` | `#3f9089` → `#0b2630` |
| rock A / B | `#0c0e16` / `#141826` | `#1a2027` / `#232b34` |
| photo | `#59ffa0` `#d8ffe8` `#1f8a52` | `#a6ff4a` `#e4ffb8` `#4f9a1e` |
| chemo | `#39f5e0` `#e0fffb` `#127a72` | `#39f5e0` `#c8fff8` `#178a80` |
| sapro | `#ffcc33` `#fff4c4` `#9a6a08` | `#ffc23a` `#fff0b0` `#a8680e` |
| pred | `#ff3fd1` `#ffd6f4` `#6a0456` | `#ff3fd1` `#ffd6f4` `#7a0a62` |
| vent | `#ff4a1a` `#ffe08a` `#6a1a08` | `#ff5a2a` `#ffd08a` `#8a2a10` |
| organic | `#3a4a80` | `#7fa39d` |

UI: background `#07080f`, panel `#0e0f1f`, primary/line `#39f5e0` (text on it `#07080f`), accent
`#ff3fd1`, milestone gold `#ffd23f`, quiet border `#2c3560`, text `#e8fbff`, secondary text `#9fd8e0`.
Touch targets ≥ 44 px. Font Pixelify Sans.
