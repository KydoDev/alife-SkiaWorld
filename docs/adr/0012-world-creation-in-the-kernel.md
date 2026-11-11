# ADR-0012: World creation in the Rust kernel

- **Status**: Proposed
- **Date**: 2026-11-11
- **Deciders**: project owner
- **Parent**: [ADR-0008](0008-engine-port-stack.md) (Rust core, bit-exact reference kernel)

## Context
G2 M5 item 9. The kernel (`engine-rs/`) runs every optional flag bit-exactly (M5 items 1-8, 18 golden sets), but it
can only **load** a world from a Python save (`engine-rs/src/save.rs`) and step it; `rng.rs:10` says so explicitly
("Seeding ... is deliberately absent"). The C ABI (`engine-rs/src/ffi.rs`, `WS_ABI_VERSION = 1` at :28) exposes load,
step and read-only views. A Unity player therefore cannot start a new world without Python.

Creating a world in Python has four parts, each with its own port difficulty:

| Part | Code | What a bit-exact port needs |
|---|---|---|
| Founders | `World.__init__` `world.py:165` (`random.Random(seed)`), `seed_population` `world.py:216-231` | Integer seeding of MT19937 (`init_by_array`). The founder loop itself is **already ported** (`world.rs:921`, used by reseed and proven by the `combined_reseed` set) |
| Procedural terrain | `generate_terrain` `terrain.py:91-103` | String seeding: `_terrain_rng` is `random.Random(f"worldsim-terrain-{seed}")` (`terrain.py:35-37`), i.e. CPython's version-2 seed, `int.from_bytes(s + sha512(s))`; `rng.uniform`; libm `sin`/`exp`; exact integer `sqrt` (`vent_plume` :56-73); `np.rint` (ties to even); and `profile.mean()` (:51), **numpy pairwise summation**, which the kernel does not have (`world.rs:104` `python_sum` is CPython's Neumaier `sum()`, a different algorithm) |
| Planet form | `config_from_form`/`planet_from_form` `worldgen.py:159-200` | JSON parsing with Python's type rules, the Python `Config` defaults (the kernel deliberately has none, `config.rs:7`), and, for a form without a seed, SHA-256 of `json.dumps(form, sort_keys=True)` (:199): CPython's JSON serialisation (float `repr`, `ensure_ascii` escapes, separators) byte for byte |
| Planet image | `_decode_image`/`terrain_from_rgb` `worldgen.py:57-103` | Pillow's decoders for five formats (JPEG IDCT, GIF palettes, lossy WEBP), `convert("RGB")` and its `BILINEAR` resample (a convolution with a widened kernel when downscaling, fixed-point coefficients) reproduced pixel for pixel; then `np.gradient`, `lum.mean(axis=0)` (a per-column reduction over a non-contiguous axis) and `sun.mean()` (pairwise) |

Two further facts: the state hash (`hash.rs`) covers `organic` (:48) but **not** the terrain maps (rock, chem, sun),
since a save carries them verbatim; and the species tracker is observer state that the kernel skips (ADR-0003), so a
kernel-made world has none.

## Options considered

### Scope
- **A. Do nothing yet**: the front-end keeps loading Python-made saves (`scripts/unity_sync.py` already copies one).
  Zero cost and zero risk. But a game cannot offer "new world" or a new seed without shipping Python, and the
  missing pieces are small, because the founder loop and the RNG draws are already ported and proven. Rejected as the
  end state; it remains the fallback if the owner puts item 10 (interventions) first, since nothing here blocks it.
- **B. Founders + procedural terrain from a full `Config` and an integer seed** (chosen). Covers the default world and
  every procedural planet (rock, vents, day/night, seasons), including `examples/volcanic.json` and
  `examples/red_dwarf.json` once Python has turned the form into a config. New code: seeding, a pairwise mean,
  `generate_terrain`, one constructor and one entry point. The input is the same `config` object a save carries, so
  it reuses the existing, reviewed, capped parser `Config::from_json` (`config.rs:32`) and needs no Rust defaults.
- **C. B + planet forms in the kernel.** Needs a second copy of every `Config` default (drift with each new field,
  one more thing to golden-test), a partial-override parser with Python's int/float/bool rules (`worldgen.py:132-144`),
  and either a port of `json.dumps` for seedless forms or a documented divergence. Its users are a Unity planet editor
  and player-shared forms, which belong to G3. Rejected for now (YAGNI). A C# mapping in the front-end is rejected
  outright: a third copy of game rules that no CI golden test can see.
- **D. C + image files decoded in the kernel.** Bit-exact equality with Pillow is not attainable in practice:
  JPEG decoders differ across implementations (libjpeg-turbo in Pillow and pure-Rust decoders round the IDCT
  differently), and the result also depends on the Pillow version. Decoding untrusted files across the FFI also
  widens the attack surface of a library that so far only parses JSON. Rejected.
- **D'. Already-decoded pixels in the kernel** (the front-end decodes and resizes; the kernel runs only
  `terrain_from_rgb` on a W x H x 3 `u8` buffer). Portable and verifiable on raw pixel arrays, but "same photo,
  same planet" across Python and Unity then fails anyway (different decoders and resamplers), and no front-end needs
  photo planets before G3. Deferred: this is the shape a future image port must take (see Decision 3).

### Seed type
`random.Random` takes any int (sign dropped), str, bytes or None (OS entropy). A kernel seed of **`u64`** covers every
seed the project produces (`run.py` and forms use 0..2^31-1, images 31 bits); None is refused, since it is
non-deterministic by definition. Negative and string seeds of the dynamics are rejected (YAGNI); the
`"worldsim-terrain-{seed}"` string is built from the `u64`'s decimal form, as Python formats it.

## Decision

1. **Scope (option B).** The kernel gains `World::new(cfg, seed: u64)`, the port of `World(cfg, seed)` with
   `terrain=None`: `generate_terrain(cfg, seed)`, `organic = terrain.organic`, then `seed_population(initial_cells)`
   on `PyRandom::from_seed_u64(seed)`. The same seed drives terrain and dynamics, as in `World.__init__`
   (`world.py:170`) and `planet_from_form` (`worldgen.py:200`). **Stays in Python**: planet forms and images (the
   authoring tools); Python exports `cfg.to_dict()` (the save's `config` object, not `run.py`'s `config.json`, which
   adds `seed` and metadata keys, `run.py:77`) for the front-end, through `scripts/unity_sync.py`. **Stays in the
   front-end**: choosing a seed and which exported config to use.

2. **Bit-exactness, part by part.**
   - *Integer seeding*: CPython `random_seed` (`_randommodule.c`): key = 32-bit words of the seed, least significant
     first, at least one word (`0` -> `[0]`), then `init_by_array` (which starts with `init_genrand(19650218)`);
     index 624, `gauss_next = None`.
   - *String seeding*: `b = s.encode()`, `n = int.from_bytes(b + sha512(b), "big")`, then the integer path on `n`
     (words from the least significant end; the top word may be partial; it is never zero because `b[0]` is `w`).
     SHA-512 comes from the `sha2` crate, already a dependency.
   - *numpy pairwise mean*: a `numpy_mean(&[f64])` helper reproducing `pairwise_sum` (sequential below 8 elements,
     eight accumulators up to 128 with the fixed combine order, recursive split rounded to a multiple of 8 above)
     **and** how the reduction seeds its accumulator (identity `0.0` or the first element). That last point is
     not settled by reading: golden vectors decide it (piece 2) before any terrain code uses the helper.
   - *Terrain maths*: Python's operation order kept literally (`2 * pi * k * x / width + u`, `0.6 / k`,
     `rock_fraction * height / mean`), libm `sin`/`exp`, exact `sqrt` of an integer `dx*dx + dy*dy`,
     `round_ties_even` for `np.rint`, clip then cast, vents summed in placement order, no `mul_add`. These are the
     rules already fixed in `docs/G2_PLAN.md` ("Rules for the port").
   - *Proof*: a new golden kind, **creation**, made by `scripts/g2_golden.py` straight from `World(cfg, seed)`, with
     no save and no warm-up. Per case it records the full config, the seed, a **terrain digest** (SHA-256 over rock
     as `u8`, then chem, sun, organic as little-endian `f64`, row-major, defined in G2_PLAN next to the state hash)
     and the step-0 state hash. Two cases also record 1000 stepped hashes from creation. These are the first hashes
     of a newborn world (age 0, initial energy), which the existing sets (warm-up 200) never cover. Seeded RNG states
     (625 words) and pairwise means join the existing raw-vector files. Per-platform sets, as decided on 2026-11-10.

3. **Untrusted input.** The only new input is a config object, parsed by the existing save path (typed, every key
   required, unknown or duplicate keys refused, `Config.validate()` bounds, `MAX_WORLD_TILES`), under a byte cap of
   64 KiB (as `worldgen.MAX_FORM_BYTES`). Creation work is bounded by the validated config: at most 10^6 tiles and
   100 vents (`config.rs:91`), so at most 10^8 plume evaluations (to be measured in piece 3; it is a one-off
   blocking call, like a large step). Floats never panic (an infinite `chem` from an extreme `vent_strength` matches
   Python's). Any future form or image port follows `worldgen.py`: byte caps checked before parsing, an error and
   never a panic, and **pixels in, never encoded files** (D').

4. **C ABI.** One new entry point:
   `WsWorld* ws_world_create(const uint8_t* config_json, size_t len, uint64_t seed)`. It returns a handle, or null
   with `ws_last_error` set (like `ws_world_load`), and its body runs inside `catch_unwind`. `WsInfo` and the existing
   signatures do not change. `WS_ABI_VERSION` goes **1 -> 2**: the front-end refuses a mismatch, and adding an entry
   point counts as a change, so an old library fails at the version check, not at the first P/Invoke. The rule for
   item 10 too: the version is **one counter for the whole ABI**, bumped once per commit that changes the ABI
   (addition, removal, signature or struct), together with the Unity wrapper. Items 9 and 10 share a bump only if
   they land in one commit. The interventions' entry points belong to the item 10 ADR. `G2_PLAN`'s FFI rule ("only
   the save loaders and `step`") gains "and `ws_world_create`"; `World::from_parts` stays unexposed.

5. **Implementation plan.** One commit per piece. Verdict rules are fixed now, before any run; all hold on Windows,
   and on Linux against CI-regenerated sets.
   1. *Seeding*: `PyRandom::from_seed_u64` and `from_seed_str`; drop the "Seeding absent" note in `rng.rs`.
      **Verdict**: the full state is equal to Python's `getstate()` for seeds 0, 1, 42, 2^31-1, 2^32-1, 2^32,
      2^63, 2^64-1 and for `worldsim-terrain-{0, 42, 18446744073709551615}`, plus 1000 `random()` draws each.
   2. *Pairwise mean*: `numpy_mean`. **Verdict**: bit-equal to `ndarray.mean()` on fixed pseudo-random data at
      lengths 1-20, 127-130, 255-257, 1023-1025, 8191-8193 and 10 000 (the largest width).
   3. *Terrain*: `generate_terrain`. **Verdict**: terrain digest equal for every case: default (flat, early
      return); `rock_fraction` only; `vent_count` only (vents on a rock-free floor, `vy = H-1`); the volcanic config;
      `rock_fraction` 0.9 with 100 vents; widths 2, 7, 8, 9, 127, 128, 129, 257 and 10 000 (height 100); 3 seeds
      each for the rocky ones. Creation time of the 10 000 x 100, 100-vent case is recorded.
   4. *World::new*: **Verdict**: step-0 state hash equal for every piece-3 case plus every founder flag on (`sex`,
      `plasticity`, `hgt`, `defence`, `open_genome`), `initial_cells = 0`, and `initial_cells` above the free tiles;
      no divergent step in 1000 for the creation sets `create_default` (seed 1) and `create_volcanic` (seed 42); the
      18 existing `hashes.csv` files byte-identical (creation is off the load and step path).
      **Non-vacuous**: the recorded cases contain rock, at least one vent and every founder draw.
   5. *FFI + Unity*: `ws_world_create`, ABI 2, FFI tests (null, empty, over the cap, not JSON, not an object,
      unknown, missing or duplicate key, out-of-range value, `u64::MAX` seed; the handle's state hash equals
      `World::new`'s), Unity wrapper and a "new world" control using a config exported by `unity_sync.py`.
      A `@code-review-security` review comes before this commit (new untrusted input across the FFI).
   - **If a verdict fails**: fix the Rust side, since every listed algorithm is deterministic and specified by
     source. Changing the Python maths (e.g. replacing `.mean()`) alters every rocky terrain, all volcanic golden
     sets and the G1 calibration: **owner's decision only**, as in ADR-0008.

6. **Out of scope.** Planet forms and images in the kernel (revisit with a G3 planet editor, in a new ADR; images
   only as pixels); content-derived form seeds; None, negative, string or bytes seeds of the dynamics; a kernel save
   writer (kernel-made worlds cannot yet go back to Python; that touches ADR-0002 and needs its own ADR); a species
   tracker in the kernel; interventions (item 10); cross-platform bit-identity (the per-platform golden sets stay).

## Consequences
- Unity can start any procedural planet from a seed without Python at run time. Python stays the planet-authoring
  tool and the reference: a `generate_terrain` rule change regenerates the creation sets in the same commit, like
  any other rule change.
- One more numpy behaviour (pairwise summation) is pinned by golden vectors. A numpy upgrade that changed it would
  show up as a creation-set failure, not as a silent drift.
- The kernel now owns two RNG constructions (integer and string seeding) beyond restoring a state. Both are covered
  by raw-state golden vectors, so a CPython change to seeding (unlikely; stable since 3.2) would also show up as a
  failure.
- Kernel-made worlds have no species tracker and cannot be saved. Both are acceptable for a viewer and an
  interventions prototype, and both are G3 work.
- Risks: (1) the pairwise reduction's initial value and block boundaries (mitigated by piece 2 running first);
  (2) worst-case creation time at 10^6 tiles with 100 vents (measured in piece 3; Python tabulates `exp` per
  distinct distance, and the kernel may do the same); (3) the exported config and the library drifting apart
  (mitigated: `Config::from_json` requires every key, so a stale config fails loudly).
