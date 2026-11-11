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
8. [~] M5 Port the optional flags (sensing, open_genome, sex, plasticity, later F flags), planets, interventions
9. [ ] M6 Optional fast (parallel) kernel, judged statistically, never claimed equivalent

## Scope of the first milestone (M0–M2)
Default flags only: `sensing`, `open_genome`, `sex`, `plasticity` off; species tracker off (it is a
pure observer and does not affect the dynamics, ADR-0003). Flat default world first, then
`examples/volcanic.json` (terrain + vents + day/night) as the second golden case.

Out of scope until M2 passes: rendering, interventions, planet loading from forms or
images (the Rust side only reads saves, which already contain the terrain maps).

## Golden data (M0)
`scripts/g2_golden.py [--planet FILE] [--set KEY=VALUE ...] --seed S --warmup W --steps N --out DIR` writes one
set; `--all ROOT` writes every set listed in `SETS` in the script (the single list: `tests/test_g2_golden.py` checks
that the committed directories and `GOLDEN_SETS` in `engine-rs/tests/common/mod.rs` match it, and CI regenerates the
Linux sets with `--all`). Committed sets: `default`, flat world; `volcanic`, `examples/volcanic.json` (terrain,
vents, day/night amplitude 1.0 and seasons 0.5, so the light factor is covered). Each set writes:
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
- **Flag fields (M5)**, only when their flag is on, so the hashes of worlds with the flag off never change:
  `hgt` adds the counters `hgt_events, hgt_foreign` (u64) after `sex_births`, then `defence` adds `defended`;
  per cell, after `sex_p`: `plast_p` and the 3 diet values (`plasticity`), `hgt_p` (`hgt`), then `armor_p`
  (`defence`), all as f64 bits; then (`open_genome`) the number of rules (u64) and each rule's 4 values as f64
  bits, in order.
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
- FFI (M4, from the M1c security review): expose only the save loaders, `ws_world_create` (ADR-0012),
  `ws_world_intervene` (ADR-0013: validated domain edits, refused with `WS_ERR_INVALID` before any write) and
  `step` (plus read-only views), never `World::from_parts` or raw field writes; wrap every entry point in `catch_unwind` (`rng.rs` still
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
  until M5 (since ported in M5, except `open_genome` so far); the species tracker is skipped, not validated (observer state, never read).
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
- **Correction** (2026-11-11): the M4 part A entry lists "the light factor (day/night, seasons) is not covered by a
  golden set" as open. It is covered: the `volcanic` set runs with `day_amplitude` 1.0 and `season_amplitude` 0.5
  (from `examples/volcanic.json`), and its 1000 stepped hashes match. Nothing is open on that point.
- **M5 item 1, golden infrastructure** (2026-11-11): `scripts/g2_golden.py` gains `--set KEY=VALUE` (as `run.py`;
  recorded in `rng.json` meta) and `--all ROOT`; the sets are listed once, in `SETS`. Regenerating both committed
  sets with `--all` gives identical `hashes.csv`, renders and RNG draws; the saves differ only in the gzip header
  time (same content). CI regenerates the Linux sets with `--all`. M5 plan and per-flag rules: `PLAN.md`.
  Review (code-review-security, no blocking issue) follow-ups, done: `--all` refuses per-set arguments and passes
  `--renders-only` on; planet paths in `SETS` resolve against the repository only; pytest checks that each committed
  set was made with the arguments `SETS` declares (seed, warm-up, steps, planet, overrides).
- **M5 item 2, `defence`** (2026-11-11, Windows 11): the kernel runs F5e prey defence. `Cell.armor_p` (founders
  draw it after their genes, children inherit it with a `gauss(0, mut_sigma)` step clamped to [0, 1]), upkeep
  `defence_upkeep x armor_p` added last in `express`, and in predation the failed-attack draw
  `random() < armor_p x defence_strength` (none in the neutral arm): a repelled attack moves no energy and counts
  in `defended`. The loader accepts `defence` and checks `armor_p` like `persistence.py` (finite, in [0, 1], zero
  unless the flag is on); the refusal tests now use `plasticity` and `hgt`. State hash: `defended` and `armor_p`
  only when the flag is on. New golden set `defence` (flat default world, `--set defence=1`). Verdict (rules fixed
  in `PLAN.md` before the run): **met**. The kernel equals Python at every one of the 1000 steps of `defence`, and
  `hashes.csv` of `default` and `volcanic` is byte-identical when regenerated. The set is not vacuous: 13002 attacks
  repelled and 12179 kills in the hashed steps (`counter_deltas` in `rng.json` meta, checked by pytest), armour
  spread over [0, 1] in the start save. Speed (M3 benchmark, default flags, before / after): 6.38 / 6.11, 8.08 / 7.92,
  5.43 / 5.54 million cell-updates/s at 800 / 10k / 50k cells, within the ±5% run-to-run spread.
  Review (code-review-security, no blocking issue; it also ran the neutral arm and a reseed-after-extinction run
  with armour against the kernel, both bit-exact) follow-ups, done: golden set `defence_neutral` (`defended` 0,
  14005 kills, equal at every step); loader test on a defence save (`armor_p` 0, -0.0, 0.5, 1 load; 1.01, -0.01,
  `true` refused); `save.rs` documents that a JSON integer `-0` in a float slot hashes differently from Python
  (Python never writes it); a comment on `first_difference`. Open, for later: `WsInfo` does not expose `defended`
  (adding it changes the layout: ABI version 2, when the front-end needs it); `default`/`volcanic` `rng.json` meta
  lacks `set` and `counter_deltas` until their next regeneration.
- **M5 item 3, `hgt`** (2026-11-11, Windows 11): the kernel runs F5c gene transfer. At the start of a cell's turn
  (before feeding), with chance `hgt_p x hgt_rate` (no draw in the neutral arm), it copies one gene (`randrange(16)`)
  from a random occupied neighbour (any lineage, bonded or not, this step's newborns included) and re-expresses its
  phenotype; `hgt_events` and `hgt_foreign` count the copies. Upkeep adds `hgt_upkeep x hgt_p` before the armour
  term; founders draw `hgt_p` before `armor_p`, children inherit `hgt_p` (clamped gauss step) before `armor_p`.
  The loader accepts `hgt` and bounds `hgt_p` like `persistence.py`; the hgt counters are now dynamic state.
  Golden sets `hgt` and `hgt_neutral`. Verdict (rules in `PLAN.md`): **met**. Both sets equal Python at every one of
  the 1000 steps, at the first run; the hashes of the four earlier sets are byte-identical when regenerated. Not
  vacuous: 26594 genes copied, 1935 of them across lineages (`hgt`); none in `hgt_neutral` (13657 kills), with
  `hgt_p` spread over [0, 1] in both. Speed: the M3 benchmark of this build and of the previous commit, run side by
  side, agree (800 / 10k / 50k: 6.05–6.20 vs 6.38, 8.03–8.71 vs 8.60, 2.84–2.89 vs 2.70 million cell-updates/s);
  the 50k world is about half its item-2 figure for both builds, so that drop is the machine's state that day,
  not the code.
  Review (code-review-security, no blocking issue) ran five extra scratch sets against the kernel, all bit-exact:
  `hgt` with `defence`, a volcanic world with `hgt_rate` 1 and large mutation steps, a 2-wide world (repeated
  neighbour tiles), the neutral defence arm with heavy immigration, and a 20x20 world with `max_age` 2 (321
  extinctions and reseeds). Open: no committed set yet combines flags or reseeds with flags on (taken into item 8);
  `WsInfo` exposes neither `defended` nor the hgt counters (one ABI version 2 change, when the front-end needs them).
- **M5 item 4, `plasticity`** (2026-11-11, Windows 11): the kernel runs F5b diet acclimation. The phenotype keeps
  the feeding shares; with the flag on, `Cell::express` resets the diet to the genetic split and `apply_diet` derives
  the photo / sapro / chemo shares and their powers from it (the predation share stays genetic; a cell with all four
  feeding genes at 0 cannot feed). Before feeding, a cell with `plast_p > 0` (not in the neutral arm) moves its diet
  towards the yield split of its tile (`acclimate`, no RNG). Founders and children draw `plast_p` before `hgt_p` and
  `armor_p`; upkeep adds `plastic_upkeep x plast_p` first. The loader accepts `plasticity`, checks `plast_p` and the
  diet like `persistence.py` (3 values in [0, 1] summing to 1 within 1e-6, empty with the flag off, frozen diets
  equal to the genetic split within 1e-9) and applies the stored diet. The render now colours cells by the phenotype
  shares, so a plastic world shows its acclimated diets, as in Python (the M4 debug assertion is gone). Golden sets
  `plasticity` and `plastic_neutral`. Verdict (rules in `PLAN.md`): **met**. Both sets equal Python at every one of
  the 1000 steps and in both renders, at the first run; the hashes of the six earlier sets are byte-identical when
  regenerated. Not vacuous: in the `plasticity` start save 538 of 555 cells have a diet more than 0.01 away from
  their genetic split, 0 of 133 in `plastic_neutral` (checked by pytest), `plast_p` spread over [0, 1] in both.
  Speed, three alternating runs against the previous commit: 800 cells +9%, 10k -4%, 50k -3% (`Cell` grows from 320
  to 384 bytes, `Phenotype` from 88 to 120); small, near the run-to-run spread, possibly a real few percent at large
  scale. Review (code-review-security, no blocking issue) ran eight more scratch sets, all bit-exact: volcanic with
  plasticity, hgt and defence together, `plastic_rate` 1, non-integer `spec_exp`, many all-zero feeding genes (the
  `non_pred` 0 and 1/3-diet branches), the neutral arm with the other flags, heavy immigration. Follow-ups, done:
  the loader's diet sum now mirrors CPython 3.12's compensated `sum()` (plain `+` disagreed with Python within an ulp
  of the 1e-6 tolerance, both ways); a test for a moved diet in the neutral arm.
- **M5 item 5, `sex`** (2026-11-11, Windows 11): the kernel runs F5a two-parent division. A dividing cell (not in
  the neutral arm) draws `random() < sex_p`, then needs energy above `sex_cost + body_cost`; it looks for a partner
  within `mate_radius` (Chebyshev, x toroidal, tiles scanned once in Python's order) whose fixed genes are closer
  than `mate_distance`, picks one at random, pays `sex_cost` and counts a sexual birth. The child's genes are a
  uniform crossover (one draw per gene) before mutation; `sex_p` is inherited from the dividing parent only and
  drawn before the other propensities, as for founders. The distance is `species.genome_distance`, i.e.
  `math.dist`, which in CPython 3.12 is not libm but its own extended-precision `vector_norm`: the kernel
  reproduces it operation by operation. Its products are `hi = x * y`, `lo = fma(x, y, -hi)`; the kernel computes the
  same pair with Dekker's TwoProduct (the rounding error of a product is unique, so the pair is identical unless a
  term underflows below ~2^-969), and uses CPython's exact frexp condition for the subnormal rescaling. A pure-Python copy of the
  algorithm equalled `math.dist` on 2M random pairs (close, sparse, nearly equal and identical genomes); the Rust
  one equals Python on 700 committed pairs, including 80 with a subnormal maximum and pairs mixing large and
  tiny differences (`scripts/g2_distance_vectors.py` -> `engine-rs/tests/genome_distance.json`,
  test `genome_distance.rs`; platform-independent, so one file serves Windows and Linux; the script records the
  Python version and refuses anything but CPython 3.12/3.13, as 3.11 has another algorithm). The loader accepts `sex`
  and bounds `sex_p`; the hash needs no change (`sex_p` and `sex_births` were always hashed). Golden sets `sex` and
  `sex_neutral`. Verdict (rules in `PLAN.md`): **met**. Both sets equal Python at every one of the 1000 steps, at the
  first run; the eight earlier sets' hashes are byte-identical when regenerated. Not vacuous: 2631 sexual births in
  `sex`, none in `sex_neutral`, `sex_p` spread over [0, 1] in both. Speed, two alternating rounds against the previous
  commit: 800 cells +2%, 10k -5%, 50k +2% (noise level).
- **M5 item 6, `sensing`** (2026-11-11, Windows 11): the kernel runs F3 directed movement. A moving cell scores
  staying put and each free, non-rock neighbour tile as `sum(weight x input) + sense_noise x random()`, one draw
  per candidate in Python's order (stay, then `NEIGH8`), none when no tile is free; inputs are the tile's light
  (/ `light_max`), organic and chemical saturation `v / (v + 1)`, and the kin, strangers and summed predator share
  among the mover's neighbours touching the tile, divided by `VIEWS` (precomputed per surface/floor row). Weights
  are `2g - 1` of genes 10-15, computed when needed (no new cell state). With `sensing` on, upkeep gains
  `sense_upkeep x sum(|w|) / 6` before the other flag terms, using CPython 3.12's compensated `sum()` (now shared by
  the loader's diet check). The loader accepts `sensing`; only `open_genome` is still refused. The hash needs no
  change (no new state). Golden sets `sensing` (flat planet) and `sensing_volcanic` (vents and rock, so the chemical
  and blocked-tile branches run). Verdict (rules in `PLAN.md`): **met**. Both sets equal Python at every one of the
  1000 steps, at the first run; the ten earlier sets' hashes are byte-identical when regenerated. Not vacuous: from
  the `sensing` start, 584 sensed-move calls and 414 moves in 20 steps; weights span [-1, 1]. Speed, two alternating
  rounds against the previous commit (flag off): 800 cells +1%, 10k +4%, 50k -1% (noise level). The review also
  ran scratch sets, all bit-exact: width 2 (aliased neighbours), 2x2 and 3x2 worlds, `light_max` 0 and subnormal,
  `sense_noise` 0 and the config bounds, and every ported flag on together; committed sets for the combinations
  belong to item 8. Regenerating all sets also refreshed the `meta` of `default` and `volcanic` (`set`,
  `counter_deltas`); their RNG vectors and hashes are unchanged.
- **M5 item 7, `open_genome`** (2026-11-11, Windows 11): the kernel runs F4 rule genes. `Cell.rules` is a list of
  4-value rules (empty for founders and with the flag off). After feeding, while not in the neutral arm, the rules
  whose condition holds (always, energy / `div_max` above or below the threshold, light here / `light_max` above
  or below) add their intensity `2v - 1` to a sensor weight, which `sensed_move` then uses, or shift the division
  threshold by `intensity x rule_div_shift x (div_max - div_min)`, clamped to [`div_min`, `div_max`]. At division
  `mutate_rules` runs after the genes and before the propensities: a gauss step on every value, then optional
  duplication (copy next to the original), deletion and a new random rule, within `max_rules`. Upkeep gains
  `rule_upkeep x len(rules)` between the sensor and plasticity terms. The loader accepts `open_genome` (every
  optional flag now loads) and checks the rules like `_valid_rules`: at most `max_rules` (none with the flag off),
  at most 64 read, each exactly 4 finite values in [0, 1]; the rules of all cells share a parse-time budget of
  4M (`MAX_TOTAL_RULES`, 128 MiB), so a hostile save is refused before every cell allocates a list (the review
  measured 2.85 GiB peak on a 3.6 MiB save without it, 780 MiB with it, inside the 1 GiB the C ABI documents). The state hash gains the rules when the flag is on
  (Python's `state_hash` and `hash.rs`, both; other sets unchanged); `first_difference` names them. Golden sets
  `open_genome` and `rules_neutral` (both with `sensing` on, since most rule targets are sensor weights): founders
  have no rules, so at the default rates only 4 of 196 cells held one at the hashed start; the sets raise
  `rule_new_rate` to 0.3 and `rule_dup_rate` to 0.2 (`RULES_TUNED` in `scripts/g2_golden.py`). Verdict (rules in
  `PLAN.md`): **met**. Both sets equal Python at every one of the 1000 steps, at the first run; the twelve earlier
  sets' hashes are byte-identical when regenerated. Not vacuous: at the `open_genome` start 123 of 231 cells hold
  rules (up to 5); in 20 steps rules changed sensor weights 2093 times and the division threshold 107 times; in
  `rules_neutral` 52 of 150 cells hold rules and none ever fires. Loader tests: 0, 1 and `max_rules` rules load;
  `max_rules + 1`, 65, values outside [0, 1], 3 or 5 values, a boolean, a bare number and an object are refused; a
  rule with the flag off is refused. Speed, alternating rounds against the previous commit (flag off): means of six rounds, 800 cells 0%, 10k +2%, 50k -2% (the first three rounds showed 50k -9%, the next three, run in the other order, +4%: noise level); Cell grows from 384 to 408 bytes (the rule Vec).
- **M5 item 8, combined sets** (2026-11-11, Windows 11): four golden sets with no new kernel code, for the
  interactions the single-flag sets cannot see. `combined`: every ported flag on (defence, hgt, plasticity, sex,
  sensing, open genome with the raised rule rates). `combined_reseed`: the same on a 4x4 world (8 founders, no
  immigration, `max_age` 30) that goes extinct 20 times in the hashed steps, so reseeded founders draw every
  propensity. `combined_width2`: the same on a 2x32 world, where a cell's left and right neighbours are the same
  tile (sensed candidates, prey, mates and gene donors alias). `open_genome_unsensed`: rule genes with sensing off,
  so only division rules act. Verdict: **met**, all four equal Python at every one of the 1000 steps at the first
  run (the item-6 and item-7 reviews had already run scratch versions); the fourteen earlier sets' hashes are
  byte-identical when regenerated. Not vacuous (pytest): in the three combined sets every counter (births, kills,
  sexual births, gene transfers, foreign transfers, repelled attacks) moved during the hashed steps, extinctions
  only in `combined_reseed`; in `open_genome_unsensed` division rules shifted the threshold in 20 steps. CI
  regenerates 18 sets on Linux now (about a minute more).
- **ADR-0012 piece 1, seeding** (2026-11-11, Windows 11): `PyRandom::from_seed_u64` and `from_seed_str` port
  CPython's `random_seed` (the seed's 32-bit words, least significant first, at least one) and `init_by_array`; a
  `str` seed is `int.from_bytes(b + sha512(b), "big")` first (`sha2`, already a dependency). Verdict (fixed in the
  ADR): **met** at the first run. The full state (624 words, index 624, no cached gauss) and a SHA-256 of the first
  1000 `random()` draws equal CPython's for seeds 0, 1, 42, 2^31-1, 2^32-1, 2^32, 2^63, 2^64-1 and the strings
  `worldsim-terrain-{0, 42, 2^64-1}`, the empty string and a non-ASCII one (`scripts/g2_seed_vectors.py` ->
  `engine-rs/tests/seed_vectors.json`, test `seed_vectors.rs`; a pytest checks the committed file against this
  Python). Platform-independent (integer arithmetic and SHA-512). No step, loader or ABI change.
- **ADR-0012 piece 2, pairwise mean** (2026-11-11, Windows 11, numpy 2.5.4): `numpy::numpy_mean` ports
  `ndarray.mean()` of a contiguous `float64` array: `pairwise_sum_DOUBLE` (plain loop below 8, eight accumulators
  up to 128 with the fixed combine order, then a split at half rounded down to a multiple of 8), divided by the
  count. The open point of the ADR, settled by the vectors: the reduction starts from the identity `+0.0` and sums
  the **whole** array pairwise; seeding the accumulator with the first element (the candidate tried first) failed
  at n = 4 and differs on 14 of the 34 lengths, a plain left-to-right sum on 18. Verdict: **met**: sum and mean
  bit-equal on lengths 1-20, 127-130, 255-257, 1023-1025, 8191-8193 (the ufunc buffer size: no chunking for
  contiguous input) and 10 000. The data of each length is drawn from `random.Random(1000 + n)` with `+` and `*`
  only, so the kernel rebuilds it with its own seeding and the file holds only results
  (`scripts/g2_mean_vectors.py` -> `engine-rs/tests/mean_vectors.json`, test `numpy_mean.rs`; a pytest ties the
  file to the installed numpy, so an upgrade that changed the summation fails there). No step, loader or ABI change.
- **ADR-0012 piece 3, procedural terrain** (2026-11-11, Windows 11): `terrain::generate_terrain` ports
  `generate_terrain` line for line: the terrain stream `random.Random("worldsim-terrain-{seed}")` (piece 1), the
  ridge profile with libm `sin`, numpy's pairwise mean (piece 2), `np.rint` as `round_ties_even`, rock below
  `H - height`, then `vent_count` vents with `randrange(W)` on top of the seabed and the plumes summed in vent order.
  `vent_plume` is public and shared with the `add_vent` intervention, so **ADR-0013 piece 1 lands here too**. The
  plume depends only on `dx*dx + dy*dy`, so the kernel tabulates it once per `(|dy|, dx)` (about `H*W/2` calls to
  `exp`, whatever the vent count), as Python does per distinct distance; the values are the same. Verdict: **met**
  at the first run: SHA-256 of rock, chem, sun and organic equal on 44 terrains (flat default and with organic;
  rock only; vents on a flat floor, `vy = H-1`; vents without strength; the volcanic form with seeds 42, 1, 2;
  `rock_fraction` 0.9 with 100 vents; `vent_radius` 1e-6; widths 2, 7, 8, 9, 127, 128, 129, 257 and 10 000 at
  height 100, three seeds each, one of them 2^64-1) and on 27 plumes (vents at `(0, 0)`, `(W-1, H-1)` and the
  centre, widths 2, 7 and 128, radius 4, 1e-6 (`exp` underflows away from the vent) and the volcanic values).
  Creation time of the largest case (10 000 x 100, 100 vents): **71 ms** in Rust (release, Windows); Python takes
  a few seconds. libm makes the digests platform-dependent, so `g2_golden.py --all ROOT` also writes
  `ROOT/terrain.json` (`scripts/g2_terrain_vectors.py`): the committed copy is the Windows reference and CI tests
  against the one it regenerates on Linux, with no workflow change. No step, loader or ABI change.
- **ADR-0012 piece 4, `World::new`** (2026-11-11, Windows 11): the kernel builds a world itself, as
  `World(cfg, seed)` with `terrain=None`: `generate_terrain` (piece 3), the initial organic field, then
  `initial_cells` founders on `random.Random(seed)` (seeding of piece 1; the founder loop was already ported for
  reseed). No species tracker, as for loaded worlds. Verdict: **met** at the first run. (1) The step-0 state hash
  equals Python's on 52 creations (`scripts/g2_create_vectors.py`, written by `g2_golden.py --all` as
  `create.json` with the full `cfg.to_dict()` of each case): the 44 terrain cases of piece 3, each founder flag
  (`sex`, `plasticity`, `hgt`, `defence`, `open_genome`) alone and together on the volcanic form, `initial_cells = 0`
  and `initial_cells` 6000 on a world with 2648 free tiles; population and `next_id` equal too. (2) Two new golden
  sets hashed from creation, `create_default` (seed 1) and `create_volcanic` (the form's seed 42, the existing
  `volcanic` set uses seed 1), with no warmup: the kernel builds them with `World::new`, equals their start save
  field by field (`first_difference`) and matches all 1000 hashed steps. They are also ordinary sets (20 now), so
  the load-and-step tests cover them. (3) A full `--all` regeneration left the 18 existing `hashes.csv` files and
  `terrain.json` byte-identical. No step, loader or ABI change; the entry point is piece 5.
- **ADR-0012 piece 5, `ws_world_create` and Unity "New world"** (2026-11-11, Windows 11, Unity 6000.5.6f1):
  the C ABI gains `ws_world_create(config_json, len, seed: u64)`, which returns a handle from `World::new`, or null
  with the reason in `ws_last_error`; **`WS_ABI_VERSION` 1 -> 2**, with the Unity wrapper. The config is the save's
  `config` object (`Config.to_dict()`), capped at 64 KiB before parsing and checked by the save path through the new
  `save::config_from_json` (scalars only, every key, no unknown key, `Config.validate()` bounds); the kernel now
  also refuses a **duplicate config key** (in saves too: Python keeps the last one, the kernel refuses the
  ambiguity, as ADR-0012 states). The body runs inside `catch_unwind`. The creation sets now carry their
  `config.json`, written by `g2_golden.py` for warm-up-0 sets. Verdict: **met**. FFI tests: both creation sets
  through the ABI over all 1000 steps in uneven chunks; the handle's hash equals `World::new` for seeds 0, 7 and
  `u64::MAX`; refused with a message: null, empty, over the cap, not JSON, not an object, a nested value, invalid
  UTF-8, an unknown, missing or duplicate key, out-of-range `width` and `rock_fraction`, a non-bool flag, too many
  tiles. Unity: `NativeWorld.Create`, a seed field and a **New world** button (Return in the field too) creating from
  `StreamingAssets/world_config.json`, which `scripts/unity_sync.py --planet` (default `examples/volcanic.json`)
  exports from a planet form; EditMode tests **10/10** in batchmode (new: both creation sets to step 100, a bad
  config's message). On-screen check of the button: by the owner. Security review before the commit: no blockers (fuzzed through the FFI in debug and release). Fixed from its should-fix list: `vent_strength` gets a finite cap of 1e6 in both engines (100 summed plumes at 1.7e308 made inf chem that no save may carry, so such a world could not be saved and reloaded); Unity reads the save and the config with the kernel's size caps before loading them, catches `ArgumentException` (an empty config file), keeps the current world if a new one fails, and parses the seed as plain digits; `unity_sync.py` reads the form through `worldgen.planet_from_form` (64 KiB cap, validation) and prints the form's own seed. Also a load-path test of the duplicate-key refusal and a memory note on `ws_world_create` (10^6 founders take about 0.4 GB). Left as known: `initial_energy`, `organic_init` and `chemo_gain` near the float maximum can still reach inf through any path (pre-existing, Python behaves the same).
- **ADR-0013 piece 2, `refresh_terrain`** (2026-11-11, Windows 11): the terrain-derived state of `from_parts`
  (`base_light`, `shade_pow`, `has_rock`, `has_chem`) moves into `World::refresh_terrain()`, the kernel's
  `World.set_terrain`, which the terrain edits of piece 3 will call; like `set_terrain` it leaves `light` alone
  (`from_parts` still starts it from `base_light`). Pure refactor. Verdict: **met**, all 20 golden sets (hashes,
  saves and both renders), the creation vectors and the FFI tests unchanged; no `hashes.csv` regenerated.
- **ADR-0013 piece 3, `World::intervene`** (2026-11-11, Windows 11): the five `play.py` edits plus `_finish_edit`
  in the kernel (`engine-rs/src/world/intervene.rs`): `Intervention` (built from the record `(kind, x, y, radius,
  amount)` by `Intervention::from_raw`, kinds 1-5, an unused argument must be exactly 0) and
  `World::intervene -> Result<u64, InterventionError>`, validated before any write (tile in the world, amounts finite
  and not negative, `-0.0` included, no nutrient sum that turns non-finite). New golden kind: `interventions.json`
  in the golden root (`scripts/g2_intervention_vectors.py`, written by `--all` after the sets, from their start
  saves): `iv_default`, `iv_volcanic`, `iv_reseed`, `iv_width2`, `iv_game`, 30 actions; after each the return value,
  state hash, terrain digest (live organic) and render SHA-256, then a hash per step to 200 steps after the last
  action. The generator chooses save-dependent tiles (a bonded cell, the strongest natural vent, the seabed, the
  ridge) from the live world and refuses to write when a non-vacuous condition fails. Verdict: **met** on the first
  run: every return value, hash, digest and render equal, no divergent step; the 20 `hashes.csv` byte-identical
  after a full `--all` into a fresh root (which also reproduced `interventions.json`). Non-vacuous (asserted by the
  generator and by the Rust test): a bonded kill, a `raise_rock` kill, both transitions of `has_rock` and
  `has_chem`, discs wrapping at `x = 0` and `x = W-1`, rows 0 and `H-1`, a capped vent on a natural vent, a
  nutrient disc over rock, the no-op returns of `raise_rock`, a vent and `dig`, an extinction caused by an edit, and
  for both early returns (`raise_rock` on rock, a vent on rock) a light left from the last step that a fresh
  `update_light` would change (each sits a step after the last refresh). Mutation check: a kernel refreshing the
  light on either early return fails the render verdict.
  Refusals (`tests/interventions.rs`): bad kinds, used unused arguments, tiles outside, NaN/inf/negative/`-0.0`
  amounts and a nutrient overflow leave the state hash, terrain digest and render unchanged; `radius = u32::MAX`
  equals `W + H`; no edit draws from the RNG. pytest: the committed file equals this Python (xfail off its OS) and
  `iv_game` ends where `play.replay` with free tools does.
- **ADR-0013 piece 4, `ws_world_intervene` (C ABI 3)** (2026-11-11, Windows 11, Unity 6000.5.6f1): the C ABI gains
  `ws_world_intervene(handle, kind, x, y, radius, amount, out_changed)` with `WS_EDIT_NUTRIENTS..WS_EDIT_VENT` (1-5)
  and `WS_ERR_INVALID = -5` (a refusal: nothing changed, `*out_changed` untouched, handle not poisoned; a panic
  still poisons); **`WS_ABI_VERSION` 2 -> 3**, with the Unity wrapper (`NativeWorld.Intervene`, `Edit`,
  `WorldSimException.Status` and the status constants). Security review before the commit: one blocker, fixed. The
  nutrient check of piece 3 refused only sums that were non-finite at once, so an edit just under `f64::MAX` was
  accepted and the next step's diffusion overflowed to inf, then NaN (unsaveable state, NaN energy). Nutrient edits
  are now refused when any edited tile would exceed `MAX_EDIT_ORGANIC = 1e12`; this is stricter than Python (no
  bound; `GameRules` adds 15.0) and only refuses, as ADR-0013 Decision 3 allows. Regression test: a whole-world edit
  at the cap, then 50 steps, all organic and energy finite. Should-fixes applied: the FFI rule above, boundary
  refusal tests compare the render too (rock, chem, light), the Unity vector test asserts step order. Review notes
  left as they are: two O(W*H) masks per nutrient call and a plume per vent call (a few ms and up to about 16 MB at
  10^6 tiles: a front-end applies edits on clicks, not every frame); a null `out_changed` on a poisoned handle
  reports `WS_ERR_ARGUMENT`. Verdict: **met**. FFI tests: every interventions case through the ABI (return value and
  hash after each action, hashes at action steps and at the end), the handle equal to `World::intervene` over five
  edits with steps between, and 17 refusals (null handle, null `out_changed`, kinds 0 and 6, `x = W`, `y = H`,
  `x = u32::MAX`, non-zero unused arguments, NaN, infinite, negative and `-0.0` amounts, sums above the cap) each
  leaving hash and render unchanged and the handle usable; the poisoned handle refuses an edit. Unity EditMode
  **12/12** (new: every interventions case through P/Invoke; a refused edit throws `StatusInvalid` and changes
  neither hash nor render).
