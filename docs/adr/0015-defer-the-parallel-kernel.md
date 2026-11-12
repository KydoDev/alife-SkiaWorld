# ADR-0015: Defer the parallel kernel (G2 M6)

- **Status**: Accepted (2026-11-12, the owner chose "defer M6")
- **Date**: 2026-11-12
- **Deciders**: project owner
- **Parents**: [ADR-0008](0008-engine-port-stack.md) (Rust core, single-threaded reference kernel)

## Context
G2 M6 is "an optional fast (parallel) kernel, judged statistically, never claimed equivalent" (`docs/G2_PLAN.md`).
`World.step()` is sequential and order-dependent: cells act in a shuffled order and each one sees the effect of the
ones before it. A parallel kernel is therefore a different simulation. The golden hashes cannot check it, only
statistics can.

Where the reference kernel stands after M6 step 1 (bit-exact field passes, `docs/G2_PLAN.md` results log):
- **Default world (160x64, about 540 cells):** about 16 000 steps/s.
- **Rich 800x320 world (about 48k cells):** 4.6-5.4e6 cell-updates/s, about 100 steps/s. That is one step per frame
  at 60 fps with headroom, the M3 target met about 3x over.
- **Not reached:** fast-forward x10 at 50k cells (3e7 cell-updates/s), still about 6x away.

No game feature planned for G3 needs 50k-cell worlds at x10. The worlds the game uses today are the default and
the example planets, far below that size.

## Options considered
1. **Defer M6** (chosen). Record the decision; reopen M6 when a concrete world needs the speed.
2. **More bit-exact optimisation now.** A hot/cold split of `Cell` (about 400 bytes, visited in shuffled order) is
   estimated at 1.5-2x at 50k cells. It is cheap and safe, but it is speed nothing needs yet (YAGNI).
3. **Design the parallel kernel now.** Strips of tiles with separate RNG streams and a statistical verdict fixed in
   advance. This is the largest piece of work, with a permanent second simulation to keep in step with Python, and
   it serves only very large worlds.

## Decision
M6 is deferred. The single-threaded reference kernel is the only kernel. G2 closes when M5 does, that is after the
owner's hand check of the Unity sandbox tools (PLAN item 9). Work then moves to G3.

**Reopen M6 when** a world the game ships, or one the owner asks for, falls below one step per frame on the target
hardware, or needs fast-forward the reference kernel cannot give. Then:
- take option 2 first, because it stays bit-exact;
- take option 3 only after that, in a new ADR, with its statistical verdict fixed before any code.

## Consequences
- **One kernel to test and to keep equal to Python:** every golden set keeps covering everything the game runs.
- **Fast-forward on very large worlds stays limited** to what the reference kernel gives, about 100 steps/s at 50k
  cells.
- **M6 step 1 stays:** it is bit-exact and verified.
