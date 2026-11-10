# G2 — Engine port plan (Rust core + Unity)

Decision: [ADR-0008](adr/0008-engine-port-stack.md) — Rust core library `worldsim-core`
in `engine-rs/`, called from Unity (`unity/`, later); same repository. Python stays the
reference lab. This file is the G2 working plan (kept apart from `PLAN.md`, which tracks
the F-phase experiments).

## Checklist
1. [x] M0 Golden vectors: `scripts/g2_golden.py` writes RNG draws + per-step state hashes from a v5 save
2. [x] M1a Rust crate skeleton in `engine-rs/`, `cargo test` green, CI job
3. [ ] M1b CPython-compatible RNG in Rust (MT19937, random, randbelow, shuffle, choice, randrange, gauss)
4. [ ] M1c Load a v5 save in Rust; state hash at step 0 equals Python's
5. [ ] M2 Port `World.step()` for default flags; per-step hash vs Python for 1000 steps; report first divergence
6. [ ] M3 Benchmark: cell-updates/s at 800 / 10k / 50k cells vs the 60 fps target
7. [ ] M4 Unity front-end: P/Invoke wrapper, render the world to a texture, play/pause/speed
8. [ ] M5 Port the optional flags (sensing, open_genome, sex), terrain/planet input, interventions
9. [ ] M6 Optional fast (parallel) kernel, judged statistically, never claimed equivalent

## Scope of the first milestone (M0–M2)
Default flags only: `sensing`, `open_genome`, `sex` off; species tracker off (it is a
pure observer and does not affect the dynamics, ADR-0003). Flat default world first, then
`examples/volcanic.json` (terrain + vents + day/night) as the second golden case.

Out of scope until M2 passes: rendering, interventions, planet loading from forms or
images (the Rust side only reads saves, which already contain the terrain maps).

## Golden data (M0)
`scripts/g2_golden.py --seed S --steps N --out engine-rs/tests/golden/<name>/` writes:
- `start.json.gz` — a v5 save at step 0 (or after a warm-up, so colonies and organic
  matter exist);
- `rng.json` — from a fixed state: 1000 × `random()`, `randrange(n)` for several `n`
  (including non-powers of two), `shuffle` of `range(50)`, `choice`, 1000 × `gauss(0, σ)`
  starting with and without a cached `gauss_next`;
- `hashes.csv` — `step,hash` for every step 1..N.

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
- **M2**: first divergent step = none in 1000 steps on both golden cases, on the owner's
  Windows machine and on the Linux CI runner. If transcendentals (`gauss`, `powf`, `sin`,
  `exp`) break it, report the step and the field that differs first, then fall back to the
  statistical test (ADR-0008) and ask the owner whether to make the Python maths portable.
- **M3**: ≥ 1.8×10⁶ cell-updates/s single-threaded (30k cells × 60 steps/s); fast-forward
  target recorded, not required.

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
  ~3 s; 265 KB of golden files. Regenerating gives identical hashes. `tests/test_g2_golden.py` (5 tests) checks
  them; stepped hashes are compared on Windows only (the other OS skips with a reason).
- **M1a** (2026-11-10): crate `worldsim-core` in `engine-rs/` (no dependencies yet), `cargo test` checks the
  golden files are present and well formed; CI job `rust-core` runs fmt, clippy and tests. Local: rustc 1.98.1.
- Open question for M2: Linux CI cannot compare stepped hashes made on Windows (maths library). Options: make
  the golden files on Linux in CI, or keep one set per OS. Decide when M2 starts.
