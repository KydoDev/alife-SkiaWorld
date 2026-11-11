# ADR-0013: Interventions through the C ABI

- **Status**: Accepted (2026-11-11: the owner confirmed the sandbox until G3, and world creation (ADR-0012) is
  implemented first, so it takes ABI version 2 and ports `vent_plume`; this ADR's FFI commit takes 3)
- **Date**: 2026-11-11
- **Deciders**: project owner
- **Parent**: [ADR-0008](0008-engine-port-stack.md) (Rust core, bit-exact reference kernel);
  ABI-versioning rule from [ADR-0012](0012-world-creation-in-the-kernel.md) (Decision 4)

## Context
G2 M5 item 10. The G1 game (`game.py`, `worldsim/play.py`) lets the player edit the world between steps. The kernel
(`engine-rs/`) cannot: its C ABI (`engine-rs/src/ffi.rs`) offers load, step and read-only views, its header says
"Nothing writes world fields" (`ffi.rs:4`), and `docs/G2_PLAN.md:127-129` forbids `World::from_parts` and raw field
writes across the boundary. A Unity player can therefore watch a world but not touch it.

`play.py` has two layers:

| Layer | Code | State it touches |
|---|---|---|
| World edits | `add_nutrients` :73-77, `meteorite` :80-87, `raise_rock` :90-102, `dig` :105-109, `add_vent` :112-122, helpers `_disc` :57-63 and `_finish_edit` :66-70 | Saved, hashed state: `organic`, cells, `deaths`; terrain `rock`/`chem` (saved, **not** in the state hash, `G2_PLAN.md:44-58`) and the caches derived from them |
| Game rules | `GameRules` :25-44 (budget, costs, radii, `nutrients_amount`, `max_chem`, milestone thresholds), `Game.act` :188-217 (bounds and budget gate, action log), `Game.step` :219-226 (regen, milestone checks), milestones :241-310, `restart` :228-238 | None of the world's: budget, achieved milestones, log, a pristine terrain copy |

Facts the port must respect:
- **The edits are pure.** No RNG draw, all integer geometry: `_disc` compares `dx*dx + dy*dy <= r*r` in int64 with
  `dx` toroidal. The one transcendental is `add_vent`'s `vent_plume` (`terrain.py:56-73`: libm `exp` of an exact
  integer `sqrt`), which ADR-0012 piece 3 ports for terrain generation anyway.
- **Return values carry meaning.** `raise_rock` returns 0 and refreshes nothing if the disc is all rock (:94-95);
  `add_vent` returns 0 on rock (:115-116) but 1 even when the capped plume changes nothing; `meteorite` returns the
  kills; `dig` always refreshes the terrain. `meteorite` and `raise_rock` call `World.kill` (`world.py:438-448`),
  which increments `deaths` (hashed) but not `kills`.
- **After an edit** `_finish_edit` runs `set_terrain` if the terrain changed (`world.py:190-211`: `base_light`,
  `has_rock`, `has_chem`, sink mask), drops dead cells in list order, and recomputes light at `world.now`, which equals
  `step_count` between steps (`world.py:512`) and after a load (`persistence.py:115`). The kernel holds the same
  caches (`world.rs:462-466`), computed once in `World::from_parts` (`world.rs:474-509`); it has no sink mask (it
  reads `rock` directly, `world.rs:1004`) and no `Terrain.organic` (`world.rs:409-413`). Light is not hashed but is
  rendered (`render.rs:32`), and the kernel's `update_light(now)` (`world.rs:967`) already takes `step_count` after a
  load (`save.rs:470`).
- **The Python log is `(step, tool, x, y)`** (`play.py:174`, :216). Radius and amounts come from `GameRules`, not
  from the log. `replay` (:313-322) applies every action whose step is `<= step_count` before the next step, in log
  order, through `Game.act`, so it re-checks bounds and budget.
- **Bad input has no Python reference.** The pure functions do not validate: a negative `y` would wrap in numpy.
  Bounds live in `Game.act` (:193) and in the front-end (`game.py:75-86`).

## Options considered

### 1. Where the game rules live
- **A. Everything stays in Python.** Unity stays a viewer. Rejected: item 10 exists to make a native front-end
  playable, and the edits are small and pure.
- **B. Only the world edits move into the kernel** (chosen). The five edits become RNG-free methods on `World`,
  validated in the core. `GameRules`, the budget, the milestones and `restart` stay in Python, which remains the
  reference. Unity gets a **sandbox**: free tools, no budget, no milestones, until G3. The edits are the only part
  that changes hashed state, so they are the only part that bit-exactness, and so the kernel, must own.
- **C. B + `GameRules`, budget and milestones in the kernel now.** The milestones need `colony_sizes`, the `seas`
  flood fill, a smoothing deque, the cataclysm state machine and a `math.hypot` test (:283, CPython's own algorithm,
  which `G2_PLAN.md:119` bans from the port), plus a second golden kind for achievement steps and budget series.
  That is G3 work (progression and UI, `ROADMAP.md:339`), and the G1 calibration ("an idle player reaches none")
  would have to be re-proved for a game Unity cannot play yet. Rejected for now (YAGNI). When G3 needs it, the kernel
  is where it goes, under its own ADR.
- **D. B + the budget and milestones in C#.** A third copy of game rules that no CI golden test can see, which is
  exactly what ADR-0012 rejected for planet forms. A budget in C# would also make Python replay depend on C#
  arithmetic matching `Game.act`. Rejected outright.

The tool parameters (radius per tool, `nutrients_amount`, `max_chem`) are `GameRules` values. To avoid a C# copy of
them, Python exports them as JSON next to the exported config (`scripts/unity_sync.py`, the ADR-0012 pattern), and the
kernel takes them as call arguments.

### 2. ABI shape
- **One entry point per edit** (`ws_world_add_nutrients`, ...): five near-identical wrappers, five validation paths,
  five `DllImport`s, and a replay log still needs a dispatcher on every side. Rejected.
- **A `#[repr(C)]` intervention struct passed by pointer**: one more layout to mirror in C# and assert (as
  `WsInfo`, `ffi.rs:64-65`), with nothing gained over scalars. Rejected.
- **One entry point, scalar arguments** (chosen). The argument list is the log record, so the front-end, the Rust
  golden harness and a Python replayer share one vocabulary: `(kind, x, y, radius, amount)`.

### 3. Action log in the ABI
A kernel-side log (stored in the handle, read through a new view) was considered. Every field of a record is known to
the caller: the arguments it passed, plus `step_count` from `ws_world_info`. A kernel world cannot be saved yet
(ADR-0012, Decision 6), so the only use of a log today is "start save + log, replayed in Python" while debugging, and
the front-end can keep that log. Rejected (YAGNI); the record format is fixed below so any later log is compatible.

## Decision

1. **Scope (option B).** The kernel gains `pub enum Intervention { Nutrients { x, y, radius, amount }, Meteorite {
   x, y, radius }, RaiseRock { x, y, radius }, Dig { x, y, radius }, Vent { x, y, max_chem } }` and
   `World::intervene(&mut self, Intervention) -> Result<u64, InterventionError>`, the port of the five `play.py`
   functions plus `_finish_edit`. It runs between steps only, draws nothing from `rng`, and returns Python's value:
   tiles changed, cells killed, or 0/1 for a vent. Game rules stay in Python. Unity's tools are a sandbox until G3,
   with parameters read from the JSON that `unity_sync.py` exports from `GameRules()`. The record of an applied
   edit is `(step_count, kind, x, y, radius, amount)`.

2. **Port rules (bit-exactness).**
   - *Disc*: `dx = |xs - x|`, `dx = min(dx, W - dx)`, inside iff `dx*dx + dy*dy <= r*r` in `u64` (with `radius: u32`
     no product overflows; Python ints are exact, so there is no rounding to match).
   - *Order*: cells are killed in list order (`order`), as `[c for c in world.cells if ...]`. Dead cells are dropped
     with the stable filter the step already uses (`world.rs:1233-1242`), and their slots go to `free_slots`. Organic
     from a meteorite is `decomp_fraction * (py_max(energy, 0.0) + body_cost)` (the death path's expression,
     `world.rs:1142`); `raise_rock` kills with 0. Bond removal keeps the order of the survivors' other bonds
     (`World::kill`, `world.rs:903-919`, reused as is).
   - *Vent*: `vent_plume` shared with terrain generation (one Rust function for both, as in Python). Then
     `added = min(chem + plume, max_chem)`, `chem = max(chem, added)`, `chem[rock] = 0.0`. Inputs are never NaN (see
     3), so plain comparisons equal `np.minimum`/`np.maximum`.
   - *Terrain refresh*: the derived part of `from_parts` (`base_light`, `has_rock`, `has_chem`) moves into one
     `World::refresh_terrain()`, called by `from_parts` and after every terrain edit, so the two cannot drift. It runs
     exactly when Python calls `set_terrain`: `raise_rock` (unless it returned early), `dig` (always), `add_vent`
     (unless it returned on rock).
   - *Light and dead cells*: the dead-cell filter and `update_light(step_count)` run exactly when `_finish_edit` runs:
     after every edit except the two early returns (`raise_rock` on all-rock, `add_vent` on rock). Those leave the
     light of the last step untouched, which differs from a fresh `update_light` because cells moved during that step,
     and the render verdict would catch the difference.
   - *Raise rock*: `rock |= mask`, `chem[mask] = 0`, `organic[mask] = 0`, in Python's order.

3. **Validation, in the core, before any mutation.** `intervene` refuses, and leaves the world bit-identical, when:
   `x >= W` or `y >= H` (as `Game.act`, `play.py:193`); an argument the kind does not use is not zero (`amount` for
   meteorite, rock and dig; `radius` for a vent), so that slot can never later change meaning silently; `amount` is
   NaN, infinite or negative (nutrients) or `max_chem` is (vent); or a nutrient amount would make any organic value on
   the tiles it edits (the disc minus rock, `play.py:74`) non-finite. That last check is stricter than Python, which has no bound because `GameRules` fixes 15.0;
   rules may refuse what Python accepts, but never change an accepted result. Any `radius: u32` is legal: a disc
   larger than the world covers it, and the work is O(W*H) per call (at most 10^6 tiles, plus 10^6 `exp` for a
   vent), bounded by `MAX_WORLD_TILES`. Since Python has no reference for bad input, refusals are tested by unit and
   FFI tests ("state hash and terrain digest unchanged"), never by golden cases. On valid input the edits index only
   validated tiles and contain no `unwrap` on caller data.

4. **C ABI.** One new entry point:
   `int32_t ws_world_intervene(WsWorld* h, uint32_t kind, uint32_t x, uint32_t y, uint32_t radius, double amount,
   uint64_t* out_changed)`, with kinds `WS_EDIT_NUTRIENTS = 1`, `WS_EDIT_METEORITE = 2`, `WS_EDIT_RAISE_ROCK = 3`,
   `WS_EDIT_DIG = 4`, `WS_EDIT_VENT = 5` (0 stays invalid, so zeroed memory is never an action; `amount` is
   `max_chem` for a vent). It runs through `with_world_mut` (`ffi.rs:94-109`): null handle or null `out_changed` ->
   `WS_ERR_ARGUMENT`; poisoned handle -> `WS_ERR_POISONED`; a refusal from Decision 3 -> a new
   `WS_ERR_INVALID = -5` with `ws_last_error` set and the handle **not** poisoned, since nothing changed (-2 is
   unused in the kernel, its tests, the wrapper and the docs, but the list is appended to, not back-filled); a panic -> `WS_ERR_PANIC` and the handle poisoned,
   because an edit may stop half-applied, exactly as a step does. `WsInfo` and the existing signatures do not change.
   These are validated domain operations, not field writes: `from_parts` and raw setters stay unexposed. The FFI
   commit rewrites `ffi.rs:3-4` and adds `ws_world_intervene` to `G2_PLAN`'s FFI rule. The C# wrapper's `Check`
   (`NativeWorld.cs:164-174`) throws on any non-zero status, so the Unity tools validate clicks first, as
   `game.py:75-78` does.

5. **Versioning (ADR-0012's rule).** One counter for the whole ABI, bumped once per commit that changes it. Items 9
   and 10 land in **separate commits with separate security reviews**, so there are two bumps. Item 10's FFI commit
   sets `WS_ABI_VERSION` to *current + 1* (3 if item 9's FFI commit, 1 -> 2, lands first; 2 otherwise), with
   `NativeWorld.AbiVersion` (`NativeWorld.cs:77`) and the wrapper's header comment in the same commit. Combining
   both into one commit was rejected: it would tie two unrelated reviews and verdicts together to save one integer.

6. **Bit-exactness proof: golden kind "interventions".** Made by `scripts/g2_golden.py`, its cases listed once in
   the script (beside `SETS`, which makes saves; these cases make none), per-platform sets. Each case starts from an
   **existing** golden save in the same golden root and holds an action list `(step, kind, x, y, radius, amount)`.
   Steps are absolute: at or after the save's `step_count` (its warm-up) and before the case's last step,
   so `replay`'s `<=` test (`play.py:318`) and an `==` test pick the same moment. The generator applies each action
   with the `play.py` function for its kind (the reference of record) at that step, before the next step, in list
   order (`replay`'s timing). Coordinates that depend on the save (the tile of maximum `chem`, a bonded colony) are
   chosen by the generator from that platform's start save and recorded, and the generator fails if a non-vacuous
   condition below is not met.
   After each action it records the return value, the state hash and the **terrain digest**: ADR-0012's definition
   (SHA-256 of rock as `u8`, then chem, sun and organic as little-endian `f64`, row-major) with organic taken from
   the live `World.organic`, because the kernel has no `Terrain.organic` and edits change the live field. At
   creation the two are equal. The digest is recorded after every action because the state hash does not cover rock
   or chem. It also records one hash per step, and an RGB render after every action (a paused player, which checks
   `base_light` and the light refresh, or its absence after an early return, directly). Radii stay small enough for
   numpy's int64 `r*r`; the kernel's `u32::MAX` radius is a unit test (same result as `r = W + H`). Cases:
   - `iv_default` (`default/start.json.gz`, flat): nutrients at `x = 0, y = 0` (wraps left, top row) with `r = 6`
     and with `r = 0`; meteorite at `x = W-1` (wraps right) with `r = 10`, hitting a bonded colony; the first rock on
     a flat world at `y = H-1` (`has_rock` false -> true); the same `raise_rock` again (returns 0, no refresh); the
     first vent (`has_chem` false -> true) next to that rock; a vent on rock (returns 0); `dig` removing all rock
     (`has_rock` true -> false); rock raised on row 0 (shades whole columns).
   - `iv_volcanic` (`volcanic/start.json.gz`, day/night, seasons): a vent on the tile of maximum natural `chem` with
     `max_chem = 4.0` (stacking capped) and again with `max_chem = 0.5` (below the natural value, which `max` keeps);
     `raise_rock` over that tile (chem zeroed under rock, the plume elsewhere kept); nutrients on a disc that overlaps
     the seabed (rock tiles skipped, the count excludes them); `dig` through the ridge; `dig` on water (returns 0,
     refreshes anyway).
   - `iv_reseed` (`combined_reseed/start.json.gz`, 4x4, all ported flags, no natural vents): a vent (`has_chem`
     false -> true), then `raise_rock` with `r = W + H` (the whole world: every cell killed, all chem zeroed so
     `has_chem` turns false again, no free tile), steps with extinctions and an empty reseed, then a whole-world `dig`
     and steps that reseed with every founder draw.
   - `iv_width2` (`combined_width2/start.json.gz`): meteorite and vent at `x = 0` and `x = 1` (`dx = min(d, 2 - d)`),
     flagged cell slots and bonds through kills.
   - `iv_game` (`volcanic/start.json.gz`): a G1-style log `(step, tool, x, y)` expanded to explicit parameters with
     `GameRules()` defaults. A pytest replays the same log with `play.replay(world, log, steps,
     GameRules(cost={t: 0.0 for t in TOOLS}))` and asserts the final state hash equals the generator's. This proves
     that the reference of record is the game's path and keeps the generator from drifting from `replay`.
   - **Verdicts** (fixed now; Windows, and Linux against CI-regenerated sets): for every action, return value, state
     hash and terrain digest equal; no divergent step from the first action to at least 200 steps after the last;
     each render byte-equal; the 18 existing `hashes.csv` (and the creation sets, if they exist by then)
     byte-identical, because edits are off the step path. **Non-vacuous**: the recorded cases show a kill of a bonded
     cell, a `raise_rock` kill, both transitions of `has_rock` and `has_chem`, discs wrapping at `x = 0` and
     `x = W-1`, rows 0 and `H-1`, a capped vent on a natural vent, a nutrient disc over rock, both no-op returns, and an extinction caused by an
     edit.

7. **Implementation plan.** One commit per piece, verdicts as above. Before each push: `pytest`, `ruff check .`,
   `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked`.
   1. *`vent_plume`*: reuse ADR-0012 piece 3 if it has landed. Otherwise port it alone here, and piece 3 reuses it.
      **Verdict**: the plume digest equals Python's `vent_plume` for vents at `(0, 0)`, `(W-1, H-1)` and the centre,
      widths 2, 7 and 128, `vent_radius` 1e-6 (`exp` underflows to 0) and the volcanic values.
   2. *`refresh_terrain`*: a pure refactor of `from_parts`. **Verdict**: all existing `hashes.csv` and renders
      byte-identical.
   3. *`World::intervene`* with validation, the golden kind, the Rust harness and the `play.replay` pytest.
      **Verdict**: Decision 6, plus unit tests showing that each refusal of Decision 3 leaves the state hash and the
      terrain digest unchanged.
   4. *FFI + C# wrapper*: `ws_world_intervene`, `WS_ERR_INVALID`, the ABI bump of Decision 5, and `ffi.rs`/`G2_PLAN`
      texts. FFI tests: null handle, null `out_changed`, poisoned handle, kind 0 and 6, `x = W`, `y = H`, non-zero
      unused argument, NaN, infinite and negative amounts, a nutrient overflow, the handle still usable after each
      refusal, and the handle's hash equal to `World::intervene`'s. **A `@code-review-security` review comes before
      this commit** (the first entry point that writes state across the FFI).
   5. *Unity sandbox tools*: `unity_sync.py` exports the `GameRules()` tool parameters as JSON; the viewer gets a
      tool selector and click-to-apply. Checked by hand in the Editor; Unity is not in CI.
   - **If a verdict fails**: fix the Rust side, since every edit is deterministic and specified by source. Changing
     `play.py`'s edits alters G1 replays and calibration: **owner's decision only**. From item 10 on, a rule change
     to a `play.py` edit regenerates the interventions sets in the same commit, like a dynamics change.

8. **Out of scope.** `GameRules`, budget, milestones and `restart` in the kernel (G3, its own ADR) and in C# (never);
   an action log in the ABI; new tools or undo; saving an intervened kernel world (the kernel save writer of
   ADR-0012, Decision 6); a species tracker in the kernel (a kill records no species death, so tracker state is not
   comparable); cross-platform bit-identity.

## Consequences
- Unity can edit a world with the five G1 tools, and the edits are proven to match Python bit for bit, including
  their effect on every later step. Python stays the reference for the edits and the only home of the game rules.
- Unity's play is a sandbox, not the G1 game, until G3: no budget, no milestones, no restart to the pristine planet
  (the front-end reloads its start save or creates a new world instead).
- An intervened kernel world cannot be saved. To reproduce one in Python, keep the start save plus the edit records.
  Replaying them needs a small Python dispatcher over the five `play.py` functions; the golden generator already
  contains one, and promoting it into `play.py` waits for a real user.
- `play.py`'s edits join the golden-tested surface: editing them now carries the cost that editing the step does.
- Risks: (1) cache drift after a terrain edit (mitigated: one `refresh_terrain` for load and edits, and the
  `has_rock`/`has_chem` transitions in the non-vacuous list); (2) a panic mid-edit leaves a half-applied world
  (mitigated: validation first, then poisoning as for a step); (3) the kernel refuses inputs Python would accept
  (non-finite organic). This is deliberate and only refuses; it never changes an accepted result; (4) the exported
  tool parameters and the library drifting apart (the JSON comes from the same Python as the config, and a missing
  key fails loudly in the wrapper).
