# ADR-0007: Two parents (evolvable sex) and save format v5

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

## Context
F5 in the roadmap groups four mechanisms (two parents, plasticity, learning, horizontal transfer). The guiding
rule is one mechanism at a time, so this ADR covers only the first, **F5a: two parents**. Choices that are
expensive to reverse:

1. Whether sex is imposed (a global switch) or evolvable, and how the propensity is stored.
2. Who can mate with whom.
3. What the offspring inherits, and who it "belongs to" for lineage and species bookkeeping.
4. Keeping the default world, and with it the G1 calibration, unchanged.

A probe before coding (no sex, 5000 steps, flat day/night + seasons and `volcanic.json`, seeds 1 and 7) found
that 85–96% of neighbouring cells are within the species distance of each other, at a median of 1–2.5
mutation steps, and only 1–6% belong to another lineage. Mates will be mostly close relatives.

## Options considered
- **Global switch** (all or no division is sexual): simple, but it can only compare worlds; it cannot show
  whether sex is *favoured* when it competes with asexual reproduction.
- **Evolvable propensity as a 17th gene**: natural, but appending a gene changes every seed's random stream
  (as F2 and F3 did) and forces a recalibration of the G1 milestones.
- **Evolvable propensity stored only when the feature is on** (like the F4 rule genes): no change to the
  off-world.
- **Partner choice**: any neighbour; neighbours within the species distance; a wider radius.
- **Recombination**: uniform crossover, one-point crossover (gene order is arbitrary here, so linkage would
  be an artefact), or averaging (blending destroys variation).

## Decision
- With `Config.sex` on, every cell has `sex_p` in [0, 1]: the probability that, when it divides, it looks for
  a partner. Seeded cells and immigrants draw it at random; children inherit it from the **dividing parent
  only**, mutated with its `mut_sigma`. Taking the mate's value half the time (the first draft) is a
  transmission bias: mates are not chosen by their propensity, so the mean falls by about
  (share of matings / 2) × variance per generation with no selection, and only in the sexual arms. It is not
  a gene: it exists, and draws random numbers, only when the feature is on.
- The partner is a random cell within `mate_radius` (Chebyshev, default 2) whose 16 fixed genes are within
  `mate_distance` (default 0.3, the same value as the species threshold but a separate field: the dynamics
  never read the species tracker). The partner contributes genes only, no energy, and is not changed.
- The child's fixed genes are a uniform crossover of the two parents (each gene from either, p = 0.5), then the
  usual mutation. Rule genes (F4), if any, come from the dividing parent. Lineage, species founder and
  bonding follow the dividing parent.
- Mating costs the dividing parent `sex_cost` (default 0), paid before its energy is split with the child.
  A cell that cannot pay `sex_cost + body_cost` does not look for a partner, so no energy goes negative; no
  partner found means an ordinary asexual division at no cost. The cost is dissipated (an energy sink, like
  upkeep and `move_cost`).
- `sex_neutral` is a control arm: `sex_p` is inherited and mutates, but mating never happens.
- **Save format v5**: each cell row gains `sex_p` (finite, in [0, 1], 0 when sex is off); counters gain
  `sex_births`. v4 saves are rejected.

## Consequences
- The off-world is bit-identical to the F4 and F3 commits (fingerprints of the full state, including floats,
  checked locally; a test asserts that no mating code runs when sex is off). The game is unaffected.
- With mates mostly close relatives, recombination mostly shuffles the recent mutations of nearby branches
  (the Fisher–Muller setting). It rarely combines innovations from distant lineages, which the roadmap hoped
  for; making that possible needs more mixing (movement, a wider radius) and is a separate experiment.
- Recombinant children sit further from the dividing parent's species founder, so speciation counts can rise
  without real invention: novelty is not compared between sexual and asexual worlds.
- A cell can mate with its own child from an earlier step (usually adjacent): effectively selfing, consistent
  with mates being close relatives.
- There is no "cost of males" (both parents reproduce, partners lose nothing); the only cost of sex is
  `sex_cost` and the break-up of good gene combinations.
