# G2 — Engine port plan (Rust core + Unity)

Decision: [ADR-0008](adr/0008-engine-port-stack.md) — Rust core library `worldsim-core`
in `engine-rs/`, called from Unity (`unity/`, later); same repository. Python stays the
reference lab. This file is the G2 working plan (kept apart from `PLAN.md`, which tracks
the F-phase experiments).

## Checklist
1. [x] M0 Golden vectors: `scripts/g2_golden.py` writes RNG draws + per-step state hashes from a save
2. [x] M1a Rust crate skeleton in `engine-rs/`, `cargo test` green, CI job
3. [x] M1b CPython-compatible RNG in Rust (MT19937, random, randbelow, shuffle, choice, randrange, gauss)
4. [ ] M1c Load a save (current `SAVE_VERSION`) in Rust; state hash at step 0 equals Python's
5. [ ] M2 Port `World.step()` for default flags; per-step hash vs Python for 1000 steps; report first divergence
6. [ ] M3 Benchmark: cell-updates/s at 800 / 10k / 50k cells vs the 60 fps target
7. [ ] M4 Unity front-end: P/Invoke wrapper, render the world to a texture, play/pause/speed
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
- Every constant comes from the loaded `Config`; unknown config keys are an error.
- Save loading in Rust validates like `persistence.py` (untrusted input) and returns an
  error, never panics.
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
