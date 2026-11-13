# ADR-0018: Species tracker in the kernel (ABI 6)

- **Status**: Accepted (2026-11-13, G3 P8; owner's choices: "bundle a tracked save", "list + ancestry",
  "species key")
- **Date**: 2026-11-13
- **Deciders**: project owner
- **Parent**: [ADR-0003](0003-species-definition.md) (the tracker is a pure observer);
  [ADR-0005](0005-sensor-genes-and-save-v3.md) (distance rescaled per gene); [ADR-0016](0016-kernel-views-for-the-front-end.md)
  (the tile word's species key); ABI-versioning rule of [ADR-0012](0012-world-creation-in-the-kernel.md); `docs/G3_PLAN.md` P8

## Context
The Unity front-end colours cells by a lineage key and has no notion of species: the kernel ignores the tracker in
saves (`save.rs` reads it as `IgnoredAny`) and never builds one. P8 wants a species drawer and the ancestry of a
species, so the kernel needs the tracker of `worldsim/species.py`. The tracker is an observer: it never draws from
the RNG and the dynamics never read it (ADR-0003), so porting it cannot change any state hash.

One fact shapes the decision: the golden start saves, and the save the APK bundles, are made with
`track_species=False`. A world loaded from such a save has cells whose species are unknown.

## Decision

### 1. The tracker, ported as written
`engine-rs/src/species.rs` reproduces `SpeciesTracker`: roots at seeding (`World::new`), at immigration and at the
reseed after extinction (origin `seed` for seeding and reseed, `immigrant` for immigrants; `speciation` for species
born of a split); `on_birth` with the dividing cell (the one that chose to mate when two parents mate), joining the parent's species when `genome_distance(child, founder) < species_threshold`, else a new species
whose parent is the parent's species; `on_death` from `kill`, which every death goes through, the deaths an
intervention causes included (Python's `play.py` and the kernel's `intervene.rs` both call `kill`); `end_step` (activity, establishment, novelty) once per
step after immigration, at the same point as Python; pruning of extinct, childless, small, never-established species,
cascading to ancestors. Species ids start at 1 (0 means "none" across the ABI). The distance is the kernel's
`genome_distance` (already golden-checked against `math.dist`). It is never called from a path that draws from the
RNG, and nothing in the step reads it.

### 2. Which worlds have one (owner: "bundle a tracked save")
- A world created by the kernel (`ws_world_create`) tracks from its founders, as `World(cfg, seed)` does.
- A save with a tracker is loaded with it; a save without one (`"tracker": null`) has none: no species list, and
  the tile key stays the lineage key. No new rule assigns species after the fact (that would be a new mechanism with
  no Python reference).
- `scripts/unity_sync.py` bundles a save made with tracking on, so the shipped world has species.

### 3. Loading a tracker is loading untrusted input
Everything Python's `_load_tracker` checks, plus what the kernel needs to never underflow or index out of range:
every id, counter and step bounded like the save's other counts; species ids unique and `<= next_id`; founder genomes
of `N_GENES` values in [0, 1]; origin one of the three names; `extinct` absent exactly for extant species; and
**each extant species' `count` equal to the number of living cells that name it** (Python does not check this; a
wrong count would make `on_death` drive a count below zero). A parent id may name a pruned species (Python looks
parents up with `.get`). The species map is bounded by the save's size cap. A security review precedes the piece
that adds it.

### 4. Not in the state hash, not saved by the kernel
The hash stays the world's (ADR-0003: tracking on or off gives the same history). The kernel cannot write saves
yet, so it does not write the tracker either. The kernel's save loader reads each cell's species id (it drops it
today) only when the save has a tracker; the cell record holds it outside the hash.

### 5. ABI 6
- `ws_world_species_info(handle, *out)`: whether the world has a tracker, extant count, retained count, next id,
  speciations, novelty, pruned.
- `ws_world_species(handle, index, *out)`: the `index`-th extant species in id order, as `WsSpecies` (id, parent or
  0, origin code, born, extinct or `u64::MAX`, count, peak, activity, established or `u64::MAX`, children).
- `ws_world_species_by_id(handle, id, *out)`: any retained species (the ancestry walk); a pruned or unknown id is
  refused with `WS_ERR_INVALID`, the handle stays usable.
- `WsCell` gains the cell's species id (0 when the world has no tracker), so its size changes.
- The tile word's key (ADR-0016 bytes 2-3) is `species id mod 65536` when the world has a tracker, the lineage key
  otherwise (owner: "species key"). The layout does not change; its meaning does, per world. Python's reference `worldsim/views.py` learns
the same rule (species id when `world.tracker` exists, lineage otherwise); `views.json` does not change, because
its worlds are the untracked golden start saves.
A world without a tracker answers `ws_world_species_info` with `tracked = 0` and refuses the other two.

### 6. Unity (owner: "list + ancestry")
A species drawer lists the extant species (tint, count, age, origin); tapping one shows its chain of ancestors back
to its root (stopping at a pruned ancestor). A full phylogenetic tree is a later piece.

## Verdict (fixed before any Rust)
`scripts/g3_species_vectors.py` writes `engine-rs/tests/golden/species.json` from Python runs with tracking on:
- created worlds: `create_default` and `create_volcanic` (config and seed of their golden sets), and created worlds
  with immigration, two parents (`sex`), gene transfer (`hgt`) and plasticity on, so every hook runs;
- a tracked save loaded mid-run (the load path);
- a tracked world with a game whose meteorites kill cells (the `survivor` script of `games.json`), so deaths by
  intervention reach the tracker;
each with the tracker's full `to_dict()`, every living cell's species id and the tile words' hash, every 100 steps.
**Pass**: the kernel's tracker equals it field by field (ids, parents, origins, founder genes bit for bit, born,
extinct, counts, peaks, activity, established, children, counters) on the golden's OS, and every state hash stays
equal to the untracked run (the observer leaves the dynamics alone).
**Not vacuous**: the generator asserts, in Python, at least one speciation, one extinction, one prune, one
established speciation-born species (novelty > 0), one immigrant root, and one species driven extinct by an
intervention across the cases. The reseed after extinction is covered only if a case reaches it; the generator
reports whether one does, and the ADR's verdict does not claim it otherwise.

## Pieces
1. Python: the vector script, `species.json`, a tracked golden save, the species key in `views.py`, pytest (the
   generator's assertions). No Rust.
2. Rust `species.rs`, the hooks, loading the tracker from a save, `golden_species.rs`; steps/s measured before and
   after (division is the hot path). No ABI change.
3. ABI 6 (Decision 5), C# mirror, FFI and EditMode tests; security review first.
4. Unity: bundled tracked save, species drawer with ancestry, species tint; then an APK.

## Consequences
- Species in the front-end mean exactly what they mean in Python's plots and `species.csv`.
- A save without a tracker stays playable but shows lineages, not species; old saves are not upgraded.
- The kernel pays the tracker's cost on every birth and death; measured in piece 2.
