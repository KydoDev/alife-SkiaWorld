# ADR-0004: Static terrain, chemosynthesis gene and save format v2

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

## Context
F2 adds a living environment: light cycles, rocks, hydrothermal vents, and a
world generated from a photo or a planet form. Three choices are expensive to
reverse:

1. Where the terrain lives and how it is reproduced. A planet generated from an
   image cannot be rebuilt from `Config` and the seed alone, and the image may be
   missing when a save is resumed (or shared with someone who never had it).
2. How vents feed cells. Chemical energy is a new niche; without a heritable trait
   to exploit it, it would just be "more light in a different place".
3. Whether the generator may draw from `World.rng`.

## Options considered
- **Terrain regenerated on load** from `Config` + seed — small saves, but breaks
  for image/form planets and silently changes old saves if the generator changes.
- **Terrain stored in the save** — larger saves (a few hundred KB uncompressed
  for 160×64, much less gzipped), but a save is self-contained.
- **Chemosynthesis via existing genes** (e.g. vents boost `photo`) — no history
  change, but conflates two niches and hides the experiment.
- **A 10th gene `chemo`**, a fourth feeding strategy normalised with
  photo/sapro/pred — a real trade-off between niches, at the price of changing
  every seed's random stream (one extra draw per genome).

## Decision
- `worldsim/terrain.py` defines `Terrain` (rock, chem, sun, initial organic).
  Procedural terrain uses its **own RNG** (`random.Random("worldsim-terrain-<seed>")`),
  never `World.rng`; default `Config` gives a flat world identical to v0's.
- Light cycles are a pure function of the step index, so they add no state.
- Gene `chemo` is appended at index 9 (existing indices keep their meaning).
- **Save format v2** stores the static maps (rock, chem, sun) unless the world is
  flat; version-1 saves are rejected with a clear message, because their 9-gene
  genomes cannot continue under the new rules (no users depend on them yet).
- Rocks: cells never occupy them, they are opaque to light, and organic matter
  does not sink into them (it settles on the seabed). Diffusion still ignores
  rocks — a documented simplification that keeps energy bookkeeping unchanged.

## Consequences
- Same seed no longer reproduces F1 numbers: F1 results remain valid for the F1
  commit; F2 baselines were re-recorded with the 10-gene engine.
- Terrain changes never shift the dynamics' random stream, so terrain variants
  of the same seed are comparable.
- Save files of image planets are self-contained and safe to share; loaders treat
  them (and planet inputs) as untrusted: shapes, finiteness and sizes are validated.
