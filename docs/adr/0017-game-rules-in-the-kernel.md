# ADR-0017: Game rules in the kernel (ABI 5)

- **Status**: Accepted (2026-11-13, G3 P7; the owner chose "P7 game rules in Rust" and, for its scope, "restart and
  saving the game later, as separate pieces")
- **Date**: 2026-11-13
- **Deciders**: project owner
- **Parent**: [ADR-0008](0008-engine-port-stack.md) (bit-exact reference kernel); [ADR-0013](0013-interventions-through-the-c-abi.md)
  (the five edits in the kernel); ABI-versioning rule of [ADR-0012](0012-world-creation-in-the-kernel.md); `docs/G3_PLAN.md` P7

## Context
The G1 game (`worldsim/play.py`) adds three things on top of the five edits the kernel already has (ADR-0013): a
divine-energy **budget** (start, cap, regeneration per step, a cost per tool), the **bookkeeping** some milestones
need (the vents the player opened, meteor strikes, a population average over a day), and five **milestones**
checked every `check_every` steps. Unity today calls `ws_world_intervene` directly: free tools, no milestones. The
game must come from the kernel so that a recorded game is checkable against Python (`play.replay`) like every other
kernel feature, and so a later iOS front-end gets the same rules.

`play.py` already promises what makes this portable: the rules draw nothing from the RNG and never change how the
simulation works, and every edit only touches saved state.

## Decision

### 1. A game is attached to a world handle
`ws_game_attach(handle, rules)` gives the world handle a game (`play.Game(world, rules)`); a second attach, or an
attach after the first step of a world created to be a game, is not needed and is refused (`WS_ERR_INVALID`). While a
game is attached:
- `ws_world_step(handle, n)` runs `Game.step()` `n` times: per step the world step, then the budget regeneration
  (`min(budget_max, budget + regen)`, once per step, never `regen * n`), the smoothed-population sample, the
  cataclysm tracking, and the milestone check when `step_count % check_every == 0`;
- `ws_world_intervene` is refused (`WS_ERR_INVALID`): player edits go through `ws_game_act(handle, tool, x, y,
  *accepted)`, which is `Game.act` (affordability, cost, vent and strike bookkeeping) and reports whether the action
  happened (refused actions are not errors);
- every read-only view (ABI 4) works unchanged.
One handle, so the front-end never holds a borrowed world pointer that a game could invalidate.

### 2. Rules cross the ABI as a fixed struct, validated
`WsGameRules` is `#[repr(C)]` with every `GameRules` field (costs and radii per tool in `TOOLS` order). Tests need
lowered thresholds (as `tests/test_play.py` does), so the rules are data, not Rust constants. They are untrusted like
a config: every float finite and in a bounded range, costs and amounts non-negative, `check_every >= 1` (it is a
modulus), radii bounded by the world size, thresholds non-negative. `ws_game_default_rules(*out)` writes
`GameRules()`, and a golden check keeps it equal to Python's defaults.

### 3. State of a game, and what it is not
Kernel state: budget (f64), milestones reached (step per milestone or none), player vents (deduplicated by tile:
`play.py`'s `break` makes duplicates count-neutral, and this bounds the list by the tile count), the current strike
record, the collapse target, the smoothing window (grown as steps run, never preallocated from `day_length`, which
may be 10^9), and the cached sea labels (reset when rock changes). No action log: `Game.actions` serves `replay` and
the restart, both outside the kernel here.
- **Not in the state hash**: the hash stays the world's. Stepping a golden set through a game with no actions must
  give its committed `hashes.csv` (this proves the rules are RNG-free and leave the simulation alone).
- **Not saved and no restart** in P7 (owner, 2026-11-13): `game.py` saves no game state today; restart needs a world
  built from the pristine terrain (`World(cfg, seed, terrain=...)`, not covered by ADR-0012's `World::new`). Each is
  a later piece with its own golden check.

### 4. Ported as written, quirks included
- A meteorite on empty water costs; a mountain on rock does not (nothing changed); a vent on rock is refused.
- `_on_strike` after a collapse opens a new strike record but keeps the collapse target.
- Total extinction (the world reseeded) cancels the cataclysm.
- Milestone texts stay in the front-end (C#), checked against `MILESTONES` by a test, like the gene names; the
  kernel reports which milestones are reached and at which step (`ws_game_info`), and the front-end announces new ones.

### 5. Arithmetic that must match Python
- Distance to a player vent: `math.hypot(dx, dy) <= abyss_radius` with integer offsets. The kernel computes
  `sqrt((dx*dx + dy*dy) as f64)` (exact integer sum, one correctly rounded sqrt), never libm's `hypot`; a pytest
  checks `math.hypot` equals that on every offset of the largest world.
- The smoothed population is `sum / len` of integer counts: an exact integer sum and one division in both languages.
- `kill_fraction * pop`, the budget and the comparisons are the same IEEE operations in the same order.

### 6. ABI 5
`ws_game_default_rules`, `ws_game_attach`, `ws_game_act`, `ws_game_info` (budget, reached mask, step per milestone,
player vent count) and the refusals in Decision 1 make ABI 5, with the C# mirror in the same commit and a
`@code-review-security` review before it (it adds an untrusted struct).

## Verdict (fixed before any Rust)
`scripts/g3_game_vectors.py` writes `engine-rs/tests/golden/games.json` from `play.Game`: per case the start save, the
rules, an action log (step offset, tool, x, y), the number of steps, and per action whether it was accepted and the
budget after it (IEEE bits), plus the milestone steps and the final state hash. Cases:
- **idle**, on `default` and `volcanic` with `GameRules()`, no actions: no milestone, and the final hash equals the
  set's `hashes.csv` at that step;
- **one case per milestone** (abyss, balance, giant, survivor, divided) with lowered thresholds where needed, at
  least one on the `plasticity` set (specialists are judged on acclimated shares);
- **budget**: a log that runs out of budget, so some actions are refused, then regenerates.
**Pass**: the Rust game gives every field equal on the golden's OS (Windows today; stepped values xfail elsewhere, as
the other golden steps do), and Python regenerates the same file.
**Not vacuous**: the generator asserts, in Python, that each milestone case reaches its milestone, that the idle cases
reach none, that at least one action is refused for budget, one meteorite on empty water is accepted, and one
mountain on rock is refused without cost.

## Pieces
1. Python: the vector script, `games.json`, pytest (the distance check, the generator's assertions). No Rust.
2. Rust `game.rs`: the rules, `Game`, `golden_games.rs` equal to `games.json`. No ABI change.
3. ABI 5: the entry points of Decision 6, the C# mirror, FFI and EditMode tests; security review first.
4. Unity: tools go through the game, budget in the HUD, a toast per milestone reached.

## Consequences
- The game is checkable against Python like the simulation; the viewer becomes the game without a C# rules copy.
- A front-end that wants free edits (a sandbox) uses a world without a game; the two modes cannot mix on one handle.
- Restart and saving games stay open (Decision 3); until then a new life is a new world handle, and quitting loses
  the budget and milestones (as in the G1 prototype).
