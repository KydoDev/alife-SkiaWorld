# G2 — Engine port plan (Rust core + Unity)

Decision: [ADR-0008](adr/0008-engine-port-stack.md) — Rust core library `worldsim-core`
in `engine-rs/`, called from Unity (`unity/`, later); same repository. Python stays the
reference lab. This file is the G2 working plan (kept apart from `PLAN.md`, which tracks
the F-phase experiments).

## Checklist
1. [x] M0 Golden vectors: `scripts/g2_golden.py` writes RNG draws + per-step state hashes from a save
2. [x] M1a Rust crate skeleton in `engine-rs/`, `cargo test` green, CI job
3. [x] M1b CPython-compatible RNG in Rust (MT19937, random, randbelow, shuffle, choice, randrange, gauss)
4. [x] M1c Load a save (current `SAVE_VERSION`) in Rust; state hash at step 0 equals Python's
5. [x] M2 Port `World.step()` for default flags; per-step hash vs Python for 1000 steps; report first divergence
6. [x] M3 Benchmark: cell-updates/s at 800 / 10k / 50k cells vs the 60 fps target
7. [x] M4 Unity front-end: P/Invoke wrapper, render the world to a texture, play/pause/speed
8. [ ] M5 Port the optional flags (sensing, open_genome, sex, plasticity, later F flags), planets, interventions
9. [ ] M6 Optional fast (parallel) kernel, judged statistically, never claimed equivalent

## Scope of the first milestone (M0–M2)
Default flags only: `sensing`, `open_genome`, `sex`, `plasticity` off; species tracker off (it is a
pure observer and does not affect the dynamics, ADR-0003). Flat default world first, then
`examples/volcanic.json` (terrain + vents + day/night) as the second golden case.

Out of scope until M2 passes: rendering, interventions, planet loading from forms or
images (the Rust side only reads saves, which already contain the terrain maps).

## Golden data (M0)
`scripts/g2_golden.py [--planet FILE] --seed S --warmup W --steps N --out engine-rs/tests/golden/<name>/`
writes (sets committed: `default`, flat world; `volcanic`, `examples/volcanic.json`):
- `start.json.gz` — a save (current `SAVE_VERSION`) at step 0 (or after a warm-up, so colonies and organic
  matter exist);
- `rng.json` — from a fixed state: 1000 × `random()`, `randrange(n)` for several `n`
  (including non-powers of two), `shuffle` of `range(50)`, `choice`, 1000 × `gauss(0, σ)`
  starting with and without a cached `gauss_next`;
- `hashes.csv` — `step,population,hash`: the start row, then every step 1..N after it.

The script lives under `scripts/` (outside the coverage gate's `worldsim/` source) and
does not change the engine. Golden files are small (a save is ~280 KB gzip; keep N ≤ 1000)
and are committed so the Rust CI job does not need Python.

### State hash (both engines, byte-for-byte the same definition)
SHA-256 over, in this order, little-endian:
- `step_count` (u64), `next_id` (u64), counters `births, deaths, kills, extinctions,
  sex_births` (u64 each);
- RNG: the 624 MT words (u32) and the position index (u32), then `gauss_next`
  (u8 flag + f64 bits);
- `organic` field, row-major, `f64::to_bits`;
- `len(cells)` (u64), then each cell **in list order**: `id, x, y` (u64/u32/u32),
  `energy` bits, `age` (u64), the 16 genes' bits, `lineage` (u64), number of bonds and
  bond ids **in insertion order**, `sex_p` bits.
Excluded: species and tracker (observer state), derived fields (`light`, phenotype),
which are recomputed and would only hide where a difference started.

## Verification criteria
- **M1b**: every golden RNG draw equal bit-for-bit.
- **M1c**: hash at step 0 equal.
- **M2**: first divergent step = none in 1000 steps on both golden cases, against the golden set made
  on the same OS (committed Windows sets locally, Linux sets regenerated in CI; see "Golden sets per
  platform"). pytest keeps its non-strict xfail for the stepped check on non-Windows. If transcendentals (`gauss`, `powf`, `sin`,
  `exp`) break it, report the step and the field that differs first, then fall back to the
  statistical test (ADR-0008) and ask the owner whether to make the Python maths portable.
- **M3**: ≥ 1.8×10⁶ cell-updates/s single-threaded (30k cells × 60 steps/s); fast-forward
  target recorded, not required.

## Coordination with F5b (plasticity, ADR-0009, on main)
F5b moves the save format to **v6** (per-cell plastic values, present only with `cfg.plasticity`) and adds
a flagged block to `step()`. With plasticity off the default world stays bit-identical to `c3e1c43` (the
engine of this branch's base, `d0e0a3d`), so the default-flags target of M0–M2 is unchanged. But
`load_world` rejects old versions: once F5b is on main, rebasing this branch makes `tests/test_g2_golden.py`
fail on the v5 `start.json.gz`. Fix then: regenerate the golden sets (the hashes should not change, since
the hash excludes the version; check that they don't) and have the Rust loader read the version current at
that point (`SAVE_VERSION` in `engine-rs/src/lib.rs`).
**Done** with F5b on main (`6f0d770`): golden sets regenerated as v6, `hashes.csv` unchanged, Rust
`SAVE_VERSION = 6`. Later F-phases follow the same rule (see "Rules for the port").

## Parallel work with the F-phases (reviewed 2026-11-10)
G2 and the F-phase plan run in parallel on these terms:
- **New F mechanisms stay behind a flag, off by default, with no RNG draws when off** (the existing rule). They
  cost the port nothing until M5.
- **No change to the default dynamics while M2 is open**: no new gene, no change to the default step order or
  RNG use, no recalibration of defaults. If one is needed, it waits for M2 or lands with regenerated golden
  sets and a note here.
- **A save-format bump** (a new cell slot, as F5a/F5b did) regenerates both golden sets in the same PR, checks
  that `hashes.csv` is unchanged, and bumps `SAVE_VERSION` in `engine-rs/src/lib.rs`. The Rust loader
  (M1c onwards) then reads the new row, ignoring the flagged fields while their flag is off.
- **A new `Config` field** (even one behind a flag) is added to `config_fields!` in `engine-rs/src/config.rs`
  in the same PR, with its type and `_BOUNDS`: the Rust loader refuses unknown config keys, and the `rust-core`
  CI job regenerates the golden saves from the current Python, so a missing field turns that job red. A new
  flag also joins the "unsupported until M5" list in `engine-rs/src/save.rs`.
- G2 milestones touch only `engine-rs/`, `scripts/g2_golden.py`, `tests/test_g2_golden.py`, this file, the G2
  section of ROADMAP and CHANGELOG/Unreleased; the shared files are the usual merge points.

## Golden sets per platform (decided 2026-11-10)
`gauss` and the stepped hashes go through the platform maths library (`log`, `cos`, `sin`, `pow`, `exp`), so
golden files made on one OS cannot be compared bit-for-bit on another. Decision (owner, after M1b's first CI
run): the committed sets in `engine-rs/tests/golden/` are the **Windows reference**; the `rust-core` CI job
regenerates both sets on Linux with `scripts/g2_golden.py` (same commands, into the uncommitted
`engine-rs/target/golden-linux/`) and runs `cargo test` against them via `WORLDSIM_GOLDEN_DIR`. Each platform
is thus compared with Python on the same platform, still bit-for-bit, never with a tolerance. Rust tests read
`$WORLDSIM_GOLDEN_DIR` and default to the committed sets. The M2 stepped hashes follow the same scheme.
pytest's non-strict xfail of the stepped check on non-Windows stays as is (it compares Python on Linux with
the Windows-made hashes). Cross-platform identity, if ever needed, is a separate question (portable maths).

## Rules for the port
- No global RNG, no `HashMap` iteration in the dynamics (use `Vec` + ids, or an
  insertion-ordered map for bonds); no `-ffast-math` equivalents, no `mul_add`.
- Transcendentals in the Python dynamics and in terrain generation go through libm (`math.exp`, `math.pow`,
  `math.sin`), never numpy's ufuncs: on AVX-512 CPUs numpy takes SIMD paths that are not correctly rounded
  (see the M2 Linux entry). This covers the light (`World.set_terrain`), the vent field (`terrain.vent_plume`,
  used by generation and by the G1 vent tool) and the seabed profile (`seabed_heights`). Distances are never
  `math.hypot` (CPython's own algorithm, not libm: it differs from `np.hypot`/UCRT on ~17% of float pairs):
  vents use `sqrt` of an exact integer `dx*dx + dy*dy`, the image gradient uses `np.sqrt(gx*gx + gy*gy)`;
  IEEE `sqrt`, `+`, `*`, `/` are correctly rounded everywhere, so numpy may vectorise them. Rust mirrors them
  with plain `sqrt` and no `mul_add`. Not a transcendental but an M5 concern: `seabed_heights` and
  `terrain_from_rgb` call `ndarray.mean()`, numpy's pairwise summation, which the port must reproduce.
- Every constant comes from the loaded `Config`; unknown config keys are an error.
- Save loading in Rust validates like `persistence.py` (untrusted input) and returns an
  error, never panics.
- FFI (M4, from the M1c security review): expose only the save loaders and `step` (plus read-only views),
  never `World::from_parts` or raw field writes; wrap every entry point in `catch_unwind` (`rng.rs` still
  has `assert!`s). Before the cdylib ships: CI builds with `--locked` and runs `cargo audit`/`cargo deny`.
- A rule change in `worldsim/` that touches the default dynamics regenerates the golden
  files in the same PR, and the Rust port follows (or the golden test is marked
  as tracking an older commit, explicitly).

## Results log
- **M0** (2026-11-10, Windows 11, Python 3.12.10): `python scripts/g2_golden.py --seed 1 --warmup 200
  --steps 1000 --out engine-rs/tests/golden/default` → start step 200 (225 cells), final population 711;
  ~3 s; 265 KB. Second set: `--planet examples/volcanic.json`, same seed/steps → start 19a6704614f8, final
  population 447; 370 KB. Regenerating gives identical hashes. `tests/test_g2_golden.py` (5 tests × 2 sets)
  checks them; stepped hashes are compared on Windows (non-strict xfail on other OSes). The gauss/random
  interleave calls `random()` while a cached gauss value is pending, so the Rust port must keep `gauss_next`.
- **M1a** (2026-11-10): crate `worldsim-core` in `engine-rs/` (no dependencies yet), `cargo test` checks the
  golden files are present and well formed; CI job `rust-core` runs fmt, clippy and tests. Local: rustc 1.98.1.
- **M1b** (2026-11-10, Windows 11, rustc 1.98.1 `x86_64-pc-windows-msvc`): `cd engine-rs && cargo test`
  → `tests/golden_rng.rs` passes on both golden sets: 1000 `random()`, 200 `randrange` (n up to 2^32+5, so
  `getrandbits(33)`), 3 shuffles of 50, 50 `choice`, 750 `gauss` + 250 `random()` interleaved (the pending
  `gauss_next` survives `random()`), and `end_state`, all bit-for-bit. Floats are compared by bits with no
  tolerance (a 2-ULP perturbation of `gauss` makes the test fail: checked). A save/restore round trip with
  a pending gauss value continues identically. Linux is unverified until the `rust-core` CI job runs: integer
  draws and `end_state` cannot differ there, `gauss` (libm log/cos/sin) may. If it does, record it here and
  decide with the M2 open question below; the comparison stays strict.
- **M1b on Linux** (2026-11-10, first `rust-core` CI run of PR #13, against the Windows-made sets): integer
  draws and `end_state` matched; 25 of 750 `gauss` draws differed by 1 ULP (platform libm). Resolved by the
  decision in "Golden sets per platform": CI now regenerates the golden sets on Linux and compares there.
  Local check of that path: sets regenerated on Windows into `engine-rs/target/golden-local/` give
  `hashes.csv` identical to the committed ones, and `WORLDSIM_GOLDEN_DIR=target/golden-local cargo test` passes.
- M2 open question (Linux vs Windows-made stepped hashes): settled by the same decision.
- **M1c** (2026-11-10, Windows 11, rustc 1.98.1): `engine-rs/src/save.rs` loads a v6 gzip JSON save
  (dependencies `flate2`, `serde` + `serde_json` with `float_roundtrip` for exact float parsing, `sha2`);
  `engine-rs/src/hash.rs` implements the state hash. `cargo test` → `tests/golden_save.rs`: the step-0 hash
  equals Python's `hashes.csv` start row on both sets (default: step 200, 225 cells; volcanic). Validation
  follows `persistence.py` and `Config.validate()` (512 MiB decompressed cap, unknown or missing config keys,
  bounds, grid/rock/duplicate checks, RNG state); ~50 malformed-save cases and 300 single-byte corruptions
  return errors, never panics. A security review (`@code-review-security`) of the first version found that a
  generic JSON tree costs ~27× the text (a 512 MiB save could exhaust memory and abort the host), that an
  oversized bond list made load and step quadratic, and that u64 counters from a save could overflow. Fixed
  before the PR: the save is deserialized into typed, **capped** structures (every list has a maximum length,
  maps share a 10⁶-element budget, the tracker and unknown keys are skipped unstored), at most 8 bonds per
  cell, every counter/id/age ≤ 2⁶², `next_id` ≥ every cell id, and the file is streamed through the
  decompressor. Deliberately stricter than Python (listed in `save.rs`): those bounds, rock as 0/1 integers,
  symmetric bonds without duplicates or self-bonds, every config key present, seed None/int/str, RNG version
  the integer 3 and words ≤ 32 bits. Saves with `sensing`, `open_genome`, `sex` or `plasticity` on are refused
  until M5; the species tracker is skipped, not validated (observer state, never read).
- **M2** (2026-11-10, Windows 11, rustc 1.98.1, Python 3.12.10, numpy 2.5.4, CPU without AVX-512):
  `engine-rs/src/world.rs` ports `World.step()` for the default flags (light with terrain, day/night and
  seasons; feeding incl. chemosynthesis; predation; random walk; sharing; death; division with mutation;
  organic diffusion/sinking/decay; immigration; reseed). `cargo test` → `tests/golden_step.rs`: **first
  divergent step = none** in 1000 steps on both sets (default 200→1200, final population 711; volcanic, 447),
  all bit-for-bit; ~11 s in a debug build including 2 × 1000 hashes. Transcendentals did not break it on
  Windows: Rust's `powf`/`exp`/`sin`/`ln`/`cos` call the same UCRT functions as CPython, and numpy's float64
  `exp`/`power` take the libm path on this CPU (its own SIMD `exp` is AVX-512 only). `shade ** k` is tabulated
  for `k = 0..H` (same values, one `pow` per row count). Sensitivity: reassociating one sum of the organic
  diffusion makes the test fail at the first step, and the diagnostic names `organic[0, 26]`. Diagnostic:
  `scripts/g2_golden.py --dump-step N` writes Python's save at step N to `engine-rs/target/g2-dumps/<set>/`;
  the stepped test then names the first differing field (`hash::first_difference`, in state-hash order).
  Same check against sets regenerated locally into `target/golden-local/` (the CI path): passes. Linux is
  verified by the `rust-core` CI job (Linux-made sets); numpy may use SVML `exp`/`pow` on AVX-512 runners, a
  risk the per-platform scheme absorbs only if Rust's libm agrees with it, so a Linux divergence there is
  recorded here, not hidden.
- **M2 on Linux** (2026-11-10): the `rust-core` job of PR #17 diverged (default at step 209, volcanic at step
  201; merged red). A throwaway diagnostic (draft PR #18, closed) showed the runner has AVX-512 (numpy finds
  `X86_V4`, `AVX512_ICL`): `np.exp(-rows/30)` differs from `math.exp` at row 36 and `np.power(0.7, k)` from
  `math.pow` at k = 4, 10, 31, 33; the first differing field was a cell's energy (photosynthesis). Owner's
  decision: compute the light's transcendentals with libm in Python (`World.set_terrain` tabulates
  `math.exp` depth and `math.pow(shade, k)`; `update_light` indexes the table). On Windows numpy already used
  libm, so the committed `hashes.csv` are unchanged (regenerated: identical over 1200 steps on both sets);
  Linux runs made before this change are no longer reproducible bit-for-bit on AVX-512 CPUs. Regression test:
  `tests/test_environment.py::test_light_transcendentals_come_from_libm`.
- **M2 open points** (2026-11-10, Windows 11, numpy 2.5.4, no AVX-512): the remaining numpy transcendentals
  moved off numpy before M5 ports terrain generation and interventions: `np.exp`/`np.hypot` of the vent field
  (generation and `play.add_vent`, now one helper `terrain.vent_plume`), `np.sin` of `seabed_heights`, and
  `np.hypot` of the image gradient in `worldgen.terrain_from_rgb`. Deviation from the brief, measured: CPython's
  `math.hypot` is not libm (differs from `np.hypot` on 33,352 of 200,000 random float pairs on Windows, while
  `np.sqrt(a*a + b*b)` differs on 0), so distances use exact `sqrt` instead. The list of every distinct `np.<name>(`
  call under `worldsim/` has no other transcendental (`**` on Python floats is CPython `pow`, i.e. libm). Checks: old vs new
  expressions equal bit for bit (plumes on 4 grid sizes with x-wrap, `seabed_heights` on 150 seeds, the
  gradient of `examples/planet.png`); both golden sets regenerated (1000 steps) → `hashes.csv`, `rng.json`
  and decompressed `start.json.gz` identical to the committed ones (volcanic has 6 vents and rock); new test
  `tests/test_environment.py::test_terrain_transcendentals_come_from_libm`. It cannot fail on this CPU even
  against the old code (numpy used libm here): it guards Linux/AVX-512 runners. Only Windows was measured: on Linux the gradient change replaces glibc `hypot` (not compared), so photo
  planets may change at the rock threshold there. Cost: `vent_field` at the
  1M-tile cap takes ~0.75 s per vent (was ~0.18 s); default worlds are unaffected (< 10 ms).
  CI (security review advisory): the `rust-core` job builds and tests with `--locked` and runs
  `cargo deny check advisories` (cargo-deny 0.20.2, prebuilt via `taiki-e/install-action`, pinned by commit
  SHA). No `deny.toml`: defaults, which also reject unmaintained crates, so a new dependency (e.g. M3's bench
  harness) may need one.
- **M3** (2026-11-10, Windows 11, Intel Core i9-14900HX, rustc 1.98.1 release, single thread):
  `python scripts/g2_bench.py --out engine-rs/target/bench` writes three step-0 saves and times Python on them;
  `cd engine-rs && cargo run --release --example bench -- target/bench 1000` steps each for 1000 steps. The
  default world is light-limited (~700 cells), so the 10k/50k worlds use `light_depth=1000, shade=0.97,
  photo_gain=4` (a 50k start on default parameters collapses to ~5k cells and mostly times the field passes).
  Cell-updates/s include the per-step O(W·H) light and organic passes. Three runs:

  | World | Mean population | Rust cell-updates/s | Steps/s | × Python (same world) | × target 1.8×10⁶ |
  |---|---|---|---|---|---|
  | 160×64, default | 537 | 5.5–5.8×10⁶ | ~10 300 | ~12–13 | ~3.1 |
  | 400×160, rich | 21 200 | 7.1–7.7×10⁶ | ~350 | ~24 | ~4.1 |
  | 800×320, rich | 48 300 | 5.2–5.4×10⁶ | ~110 | ~26 | ~2.9 |

  **M3 target met** about 3× over: ~48k cells at ~110 steps/s, i.e. 1 step per frame at 60 fps with headroom.
  Fast-forward ×10 at 50k (≈3×10⁷) is **not** reached by the reference kernel (recorded, not required; M6).
  Correctness at scale: the kernel's hash equals Python's after the steps Python timed (200 / 40 / 10) on all
  three worlds. The speed-up over CPython (12–27×) is below ADR-0008's 30–100× estimate; the kernel is
  unoptimised (it copies the organic field and the config every step, `Vec` bonds), so there is room before M6.
  Timings vary ±5% between runs; Python's baseline is the first steps of each world (a transient).
- **M4 part A, C ABI** (2026-11-11, Windows 11): `engine-rs/src/ffi.rs` exposes an opaque world handle
  (`ws_world_load` from gzip bytes, `ws_world_free`), `ws_world_step`, read-only views (`ws_world_info`,
  `ws_world_state_hash`, `ws_world_render_rgb`), `ws_last_error` (per thread) and `ws_abi_version` (1). Every entry
  point checks null pointers and exact buffer sizes and runs in `catch_unwind`; a panic in a step poisons the handle.
  Nothing writes world fields. The Rust loader now computes the light at load like `persistence.py` (light is not
  hashed: `hashes.csv` unchanged). `render.rs` ports `render.py` keeping numpy's float32/float64 promotions; it equals
  Python byte for byte on the loaded start save and after 1000 steps, both sets (`render_start.rgb.gz`,
  `render_end.rgb.gz`, written by `scripts/g2_golden.py`, `--renders-only` for existing sets). `tests/ffi.rs`: golden
  hashes through the ABI in uneven chunks, bad and refused saves with their message, null handles, wrong buffers,
  error truncation; a unit test checks the poisoned handle. Checked from outside Rust with Python `ctypes` on the
  built `worldsim_core.dll` (volcanic, 1000 steps: hash equal).
  Security review (no blocking issue) follow-ups, done: error messages capped at 512 bytes while formatting (a
  hostile save echoed a 10 MB string into the error), read-only calls take a shared reference, `ws_last_error` and
  `set_error` never panic (`try_with`), a build with `panic = "abort"` fails to compile, compressed saves above
  256 MiB refused, `WsInfo` layout asserted (48 bytes), panic text kept in the message. Open, for later: the
  light factor (day/night, seasons) is not covered by a golden set (both have it off); render reads the genes,
  so plasticity at M5 must switch it to the diet (a debug assertion marks it).
- **M4 part B, Unity front-end** (2026-11-11, Windows 11, Unity 6000.5.6f1): project in `unity/`.
  `NativeWorld.cs` wraps the C ABI (P/Invoke, `SafeHandle`, refuses a DLL with another ABI version, kernel
  errors become `WorldSimException` with the kernel message). `WorldSimView` renders into an RGB24 texture
  (point filtering, rows flipped so the surface is on top), IMGUI bar with play/pause, step and speed
  (1–480 steps/s, at most 20 steps per frame). The DLL and a save are copied in by `scripts/unity_sync.py`
  (git-ignored); the scene is generated by `WorldSimSetup.CreateScene`. EditMode tests in batchmode, 7/7:
  ABI version, golden hashes through P/Invoke in uneven chunks (both sets), start render equal to Python's
  byte for byte (both sets), bad save and short buffer raise with the kernel message, disposed world throws.
  A Windows player build loads the default golden save and runs at 30 and 60 steps/s; checked on screen
  through screenshots (surface on top, controls working). Not in CI (licence). Observed once and not
  reproduced in two tries: after a click on `+`, `Space` left the player paused; recorded, not fixed.
