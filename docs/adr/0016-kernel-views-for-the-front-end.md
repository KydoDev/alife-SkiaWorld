# ADR-0016: Kernel views for the front-end (ABI 4)

- **Status**: Accepted (2026-11-12, G3 P4; the owner asked to go ahead with P4)
- **Date**: 2026-11-12
- **Deciders**: project owner
- **Parent**: [ADR-0008](0008-engine-port-stack.md) (Rust core, bit-exact reference kernel); ABI-versioning rule
  from [ADR-0012](0012-world-creation-in-the-kernel.md) (Decision 4); `docs/G3_PLAN.md` P4

## Context
The Unity front-end sees a world only as `ws_world_render_rgb` (one RGB pixel per tile) plus `WsInfo`
(`engine-rs/src/ffi.rs`). The later G3 phases need more:
- **P5 sprite renderer**: what stands on each tile (which diet, bonded or not, how full, which lineage), uploaded once
  per frame as a data texture;
- **P6 inspector and population chart**: one cell's genes, energy, age, diet, bonds and colony size; counts per diet;
- **HUD**: the day/season light factor.

The views must be read-only: no RNG draw, no state change, the state hash untouched. Python is the reference for every
value, as for the rest of the kernel.

## Decision

### 1. `ws_world_tiles(handle, out, len)`: one 32-bit word per tile
`len` is in bytes and must equal `width * height * 4`, tiles row-major, row 0 = the lit surface. The word is written
little-endian, byte by byte (no alignment demand on `out`), so the buffer is directly an RGBA32 texture; each field
sits inside one byte, so a shader never joins bits across channels.

| Byte (channel) | Bits | Field |
|---|---|---|
| 0 (R) | 0-2 | **kind**: 0 no cell; else `1 + index` of Python's `Cell.strategy`: the largest of (photo, sapro, pred, chemo), the first in that order on a tie. So 1 photo, 2 sapro, 3 pred, 4 chemo. (The plan's list had another order; this one follows `strategy` and `render.rs`.) |
| 0 (R) | 3 | **bonded**: the cell has at least one bond |
| 0 (R) | 4 | **rock** |
| 0 (R) | 5-6 | **chem level** 0..3: `min(3, floor(clip01(chem) * 4))`, the vent field as `render_rgb` clips it (the save holds the field, not vent positions) |
| 0 (R) | 7 | 0 (reserved) |
| 1 (G) | 0-3 | **energy level** 0..15: `floor(16 * (energy / div_thr))`, clamped to [0, 15]; a NaN gives 0. `div_thr` is the cell's own division threshold, so 15 means "about to divide"; it can be exactly 0 (`div_min` may be 0), and the division then follows IEEE-754 (a positive energy gives 15, 0 or NaN gives 0), never an error |
| 1 (G) | 4-7 | 0 (reserved) |
| 2-3 (B, A) | 0-15 | **species key**: `lineage mod 65536` (lineage until P8 ports the species tracker). Lineages are founder or immigrant cell ids, so two lineages can share a key after 65536 ids; P5 maps the key to a tint, where a rare shared colour is acceptable. 0 when there is no cell (kind tells the two apart) |

Empty tiles carry only rock and chem. The background (water by light, organic matter, vent glow) is **not** in the
word: P5 keeps `ws_world_render_rgb` as the background layer below 5 px per tile and under the sprites, so today's
look stays golden-checked and the word stays 4 bytes.

### 2. `ws_world_cell(handle, x, y, out)`: the inspector record
A fixed-size, blittable `WsCell` (248 bytes, 8-byte aligned; a compile-time assert like `WsInfo`'s):

| Field | Type | Value |
|---|---|---|
| `id`, `lineage`, `age` | u64 | as saved |
| `energy` | f64 | |
| `genes` | f64 x 16 | the fixed genome, `GENE_NAMES` order |
| `shares` | f64 x 4 | photo, sapro, pred, chemo: the feeding shares the render uses (from the acclimated diet when plasticity is on) |
| `traits` | f64 x 5 | `TRAITS` order (ADR-0014): sex_p, plast_p, hgt_p, armor_p, sense_r; each 0 while its flag is off (sense_r always 0: the kernel refuses `sense_range`) |
| `present` | u32 | 1 if a cell stands on (x, y), else 0 and every other field 0 |
| `bonds` | u32 | number of bonds |
| `colony` | u32 | cells in its bonded component, itself included; **1 for an unbonded cell** (`play.colony_sizes` skips those) |
| `rules` | u32 | number of F4 rule genes |

The traits are in the record now, so adding them later is not another ABI bump. An empty tile is not an error
(`WS_OK`, `present` 0); a tile outside the world is `WS_ERR_INVALID` and does not poison the handle.

### 3. `WsInfo.light_factor` (f64)
`World.light_factor(step_count)`, the factor of the light field the world holds between steps (`update_light` runs at
`now`, which equals `step_count` after a step and after a load) and the value `stats()` reports before rounding it to 4 decimals. `WsInfo` grows from
48 to 56 bytes.

### 4. ABI 4, in one commit
The three changes bump `WS_ABI_VERSION` to 4 in the same commit as the C# mirror (`NativeWorld.AbiVersion`, `WsInfo`,
`WsCell`), so `main` never holds a Unity project that refuses its library.

### 5. Reference and golden
`worldsim/views.py` is the Python reference (`tile_words`, `cell_record`, `colony_size`), headless and covered by
pytest. `scripts/g3_view_vectors.py` writes `engine-rs/tests/golden/views.json`: for the `default`, `volcanic` (day and
season on, vents), `plasticity` and `combined` sets, at their start save and after 37 more steps, the SHA-256 of the
tile bytes, `light_factor` and some cell records (floats as IEEE-754 hex), cells picked by a fixed rule (the first,
the last and the bonded ones in grid order, up to 8). The Rust tests and the Unity EditMode tests compare against it
byte for byte, and check that the state hash is unchanged by the views.

## Consequences
- P5 and P6 read everything they need without new entry points; the population chart counts the kind field.
- Two copies of the packing rules (Python, Rust) and a third reader (C#, which only unpacks); the golden file keeps
  them equal.
- The species key is a lineage key until P8; P8 changes its meaning, not the layout (the reserved bits stay free for it).
- Golden view vectors depend on the platform's libm like the other sets (`volcanic` steps through `sin`).
