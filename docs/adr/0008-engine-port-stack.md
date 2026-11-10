# ADR-0008: Engine port stack for G2

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

## Context
G2 ports the engine so the game can run tens of thousands of cells at 60 fps. The
roadmap names two options: (1) Unity + C# with Jobs/Burst (or compute shaders), (2) a
Rust core library called from Unity. Python stays the reference lab. The choice is
expensive to reverse: it fixes the language of the second engine, how it is tested
and who can maintain it.

Facts from the current engine (`worldsim/world.py`, `persistence.py`) that constrain
any port:

1. **The step is sequential and order-dependent.** `step()` shuffles `cells`, then each
   cell in turn eats organic matter, kills a neighbour, moves, shares energy with its
   colony and divides. Later cells see the effects of earlier ones in the same step.
   A parallel update (Jobs over cells, a compute shader) is a *different simulation*,
   not a faster one: it cannot be checked against Python, and it changes the science.
2. **RNG.** All randomness is CPython's `random.Random` (MT19937). The save stores the
   full `getstate()`, including the cached `gauss_next`. The draws used are `random()`,
   `shuffle`, `choice`, `randrange` (integer rejection sampling over `getrandbits`)
   and `gauss` (Box–Muller with `log`, `sqrt`, `cos`, `sin`).
3. **Floating point.** Cell updates are plain IEEE-754 `+ − × /` (portable). The
   exceptions are transcendental: `gauss` (each mutation), `np.exp` (base light, once),
   `np.power(shade, above)` (light, every step) and `math.sin` (day/season factor,
   every step). `stats()` also uses `organic.sum()` (numpy pairwise summation).
4. **Performance today**: ~540 steps/s at ~800 cells ≈ 4×10⁵ cell-updates/s (F1
   profile; F3 sensing costs ~30%). Default world 160×64.

### What "tens of thousands of cells at 60 fps" needs
At one step per frame, 30 000 cells × 60 = 1.8×10⁶ cell-updates/s (≈ 4× Python);
50 000 cells = 3×10⁶. A fast-forward of ×10 needs 2–3×10⁷. Compiled single-threaded
code typically runs this kind of branchy object loop 30–100× faster than CPython
(estimate, to be measured in milestone M1), i.e. ~10⁷–4×10⁷ cell-updates/s. So **a
single-threaded, order-preserving port should meet the 1×-speed target**, and
fast-forward is where extra speed would be needed. The grid fields (light, organic
diffusion) are O(W·H) array passes and can be vectorised or parallelised without
changing results, because they are elementwise.

Consequence for both options: the port has a **reference kernel** (sequential, same
order and RNG stream as Python) and may later get a **fast kernel** (parallel) only as
a separate, explicitly non-equivalent mode, judged statistically.

## Determinism and cross-engine verification (applies to both options)

Three tiers, stated honestly:

| Tier | What | Portable bit-exactly? |
|---|---|---|
| Integer RNG | MT19937 state from the save; `random()` = `(a>>5, b>>6)` → 53-bit; `getrandbits`/`_randbelow` for `shuffle`, `choice`, `randrange` | **Yes**, by reimplementing CPython's algorithms (pin Python 3.12) |
| Plain float maths | energy, organic diffusion/sinking/decay, sharing | **Yes**, if the compiler does no FMA contraction, reassociation or fast-math |
| Transcendentals | `gauss` (log/sin/cos), `np.power`, `math.sin`, `np.exp` | **Unverified.** CPython `math.*` calls the C runtime; numpy may use its own SIMD loops; .NET `Math.*` and Rust `f64` methods call the platform libm; Burst uses its own maths library. Equal on the same OS is plausible, not guaranteed |

There is no "roughly the same trajectory": one ULP of difference eventually flips a
threshold (`rand() < p`, `energy >= thr`) and the runs diverge. So equivalence is
measured as:

- **Golden test (bit-exact)**: from a v5 save, both engines run N steps; compare a
  full-state hash every step. Report the **first divergent step** (∞ = pass). Target:
  ∞ for N = 1000 on the default world (sensing, open_genome, sex off) on the owner's
  Windows machine.
- **Statistical test (fallback, and for any fast kernel)**: K seeds per engine
  (K ≥ 10), compare population, strategy shares and gene means over time; pass if the
  per-step means differ by less than the between-seed spread (two-sample test on
  time-averaged columns, threshold fixed before running).
- **Golden vectors** produced by a Python script (`scripts/g2_golden.py`): raw RNG
  draws (`random`, `randrange`, `shuffle`, `gauss`) from a known state, and per-step
  hashes from a v5 save. They pin down the RNG port before the step is ported.
- If transcendentals prevent bit-exactness, one option is to change the Python maths
  (e.g. light via repeated multiplication, a portable `log/sin/cos`). That breaks
  bit-identity with every earlier run and the G1 calibration: **owner's decision
  only**, not part of this ADR.

Where the test runs matters as much as what it checks: a core with **no `UnityEngine`
dependency** (plain C# under `dotnet test`, or Rust under `cargo test`) can run in CI
next to `pytest`. Code that runs only inside the Unity editor cannot.

## Options considered

### Option 1 — Unity + C# (core as a plain .NET library; Jobs/Burst later)
The core is a C# class library (`netstandard2.1`) with no Unity references, used by a
Unity project through an assembly definition / DLL and tested with `dotnet test`.
Jobs/Burst (or compute shaders) only for the fields and any future fast kernel.

- **Determinism**: good for the reference kernel. C# `double` + `-` × / are IEEE;
  RyuJIT does not contract to FMA on its own. `Math.Log/Sin/Cos/Pow` call the C
  runtime on Windows (same family as CPython there). **Burst** (`FloatMode.Strict`
  still uses Burst's own maths functions) will likely not match the transcendentals
  bit-for-bit, so Burst code stays out of the reference kernel.
- **Verifiability**: high, with `dotnet test` in CI on Windows/Linux runners. Unity's
  Mono/IL2CPP backends are another compiler: the golden test must also run once inside
  Unity (Unity Test Framework, edit mode) before a release.
- **Performance**: managed C# with `class Cell` objects is ~10–30× CPython (estimate);
  struct-of-arrays + Burst much more but changes the code shape. Meets 1× likely; fast-
  forward ×10 at 50k cells is uncertain without Burst.
- **Maintenance (one hobby developer)**: one language in the game; Unity tooling and
  Unity MCP already installed. Two engines
  (Python + C#) to keep in sync on every rule change.
- **Risk**: Unity's licence/runtime terms are outside the project's control (the core
  library itself is plain .NET and survives a change of front-end).

### Option 2 — Rust core (`cdylib`) called from Unity
The core is a Rust crate (`worldsim-core`), exposing a C ABI; Unity calls it through
P/Invoke. Tested with `cargo test`; Python can also call it (PyO3) for lab speed-ups.

- **Determinism**: best control. `f64` ops are IEEE, no FMA contraction or fast-math
  unless asked; transcendentals can come from the platform libm or from the pure-Rust
  `libm` crate (identical on every OS, but then *not* CPython's — see the tier table).
- **Verifiability**: high, `cargo test` in CI; the same binary runs in Unity, so no
  second compiler. A PyO3 binding would let pytest call the Rust core directly: the
  strongest cross-engine test of the two options.
- **Performance**: highest (~50–100× CPython for this loop, estimate); data-parallel
  field passes with `rayon` without changing results.
- **Maintenance**: three languages (Python lab, Rust core, C# glue in Unity); an FFI
  boundary to keep safe (ownership of buffers, panics across FFI, per-platform native
  builds for Windows/macOS/Linux/mobile). Rust is a new language to learn if not
  already known. Two engines to keep in sync, as in option 1.
- **Bonus**: the core is reusable outside Unity (Godot, web via WASM, Python lab).

### Scores (1 = poor, 5 = best)

| Criterion | 1. Unity + C# | 2. Rust core + Unity |
|---|---|---|
| Determinism (RNG stream, iteration order, floats) | 4 | 5 |
| Verifiable against Python (golden + statistical, in CI) | 4 | 5 |
| Performance (≥ 30k cells at 60 fps, fast-forward) | 3 (4 with Burst) | 5 |
| Maintenance cost for one hobby developer | 4 | 2 |
| Reuse outside Unity | 3 (plain .NET lib) | 5 |

Both options can meet the 1× target with a sequential reference kernel; the difference
is headroom (Rust) versus a single game-side language and lower upkeep (C#).

## Also expensive to reverse: repository layout
- **A. Same repository** (`engine-cs/` or `engine-rs/` beside `worldsim/`, Unity project
  in `unity/`): golden vectors and both engines move together in one PR; CI runs pytest
  and the port's tests together. Unity projects are large (Library/ is git-ignored, but
  assets grow).
- **B. Separate repository** for the Unity game, with the core in this repo: keeps this
  repo a small research project; the game pins a core version.

## Decision
The owner chose (2026-11-10) **option 2, a Rust core library called from Unity**, and
**layout A, the same repository**:
- `engine-rs/` holds the Rust crate `worldsim-core` (the reference kernel) beside
  `worldsim/`; the Unity project will live in `unity/` when the front-end starts.
- The reference kernel is sequential, preserves Python's iteration order and RNG
  stream, and has no game-engine dependency; it is verified by golden tests
  (`cargo test`) that run in CI next to `pytest`.
- Python stays the reference: rules change there first, then in the port.
- Parallel kernels are separate modes and are judged statistically, never claimed
  equivalent.
- Transcendentals start on the platform libm (closest to CPython on the same OS); if the
  golden test diverges there, the fallback is decided by the owner (see the tier table).

## Consequences
- Three languages to maintain (Python lab, Rust core, C# glue in Unity) and an FFI
  boundary: no panics may cross it, buffers are owned by Rust and copied out.
- CI gains a Rust job (`cargo test`, `cargo clippy`); the golden vectors are produced by
  `scripts/g2_golden.py` and committed, so CI does not need both engines in one job.
- Native builds per platform are needed before the game ships (Windows first).
- A PyO3 binding becomes possible later (Rust core as a fast lab backend), but is out of
  scope until the port passes the golden test.
- Every rule change in `worldsim/` now has a port cost; the roadmap's F-phases keep
  running in Python and are ported in batches, not one by one.
