# ADR-0003: Species definition and novelty metric

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

## Context
F1 asks for a species tree and a "novelty over time" chart. Genomes are 9
continuous values, so every newborn is genetically unique: a species must be
defined by a rule. The roadmap will use the novelty signal to decide when to
move to an open genome (F4), so the metric must be honest about what it measures.
Immigration adds ~0.5 random root lineages per step, which would dominate any
naive novelty count.

## Options considered
- **Periodic clustering of living genomes** (k-means / DBSCAN every N steps) —
  no ancestry, clusters must be matched across time; heavy.
- **Per-cell genealogy** — exact, but memory grows with every birth (millions).
- **Threshold speciation on a fixed founder genome** (NEAT-like, incremental) —
  a child stays in its parent's species while its genome is within a distance
  of the species founder; otherwise it founds a child species. Cheap, gives
  ancestry directly, one tunable threshold.

## Decision
Threshold speciation (`worldsim/species.py`): Euclidean distance to the founder
genome, `species_threshold = 0.3`. Seeded and immigrant cells are roots.
Novelty is a **simplified evolutionary activity** after Bedau & Packard: each
species accumulates population-steps; it is *established* when that reaches
`novelty_activity = 1000`; novelty counts established species **born by
speciation** (roots excluded). Extinct, childless, never-established species with
peak < `species_prune_peak = 5` are pruned to bound memory.

The tracker is a **pure observer**: it never draws from the world RNG and the
dynamics never read it. Tests prove identical per-cell histories with tracking
on/off and with different thresholds, so the definition can be revised by
replaying a seed.

## Consequences
- No neutral shadow model: `novelty_activity` is an arbitrary threshold, not a
  significance level. Compare novelty curves between runs, not absolute values.
- The threshold sets species granularity (seed 1: ~80–280 extant species for
  ~800 cells). Changing it changes the tree, never the simulation.
- Memory: established species are kept forever (~0.4 retained per step at
  default settings); revisit if runs reach 10⁶ steps.
- Tracking costs ~4% of step time.
