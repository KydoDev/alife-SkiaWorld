# ADR-0011: Prey defence and save format v8

- **Status**: Accepted
- **Date**: 2026-11-11
- **Deciders**: project owner

## Context
Learning (F5d), the F3 re-run and a pilot of memory regulators were inert for one reason: median life is 6-8 steps.
A world study found that 96-97% of deaths are kills and that predation is diffuse (most kills come from mostly photo
or chemo cells with a small predatory share). No setting of the existing parameters gave a stable long-life world:
the best failed a 30k-step check on 20 pairs (7/20). The owner chose a new mechanism, prey defence.

Choices that are expensive to reverse:
1. How defence acts on predation, and whether predators get a counter-trait.
2. Whether defence is a gene or a value outside the genome, and the save format.
3. ADR-0010 said that a fourth per-cell value outside the genome should trigger an "extended genome" refactor.

## Options considered
- **Effect**: a failed attack (probability per attack), a higher energy cost for the predator, or protection from
  bonds only. A failed attack is the simplest lever on the cause found (diffuse kills).
- **Gene vs propensity**: a 17th gene changes every seed's random stream (mutation draws one value per gene), so the
  default world would no longer be bit-identical. A propensity outside the genome keeps it bit-identical.
- **Counter-trait for predators** (an arms race): a second mechanism; later and separate.
- **Extended-genome refactor now** vs later.

## Decision
- With `Config.defence` on, each cell has an evolvable `armor_p` in [0, 1] (seeded and immigrant cells draw it after
  `hgt_p`; children inherit it mutated with `mut_sigma`). An attack on a cell fails with probability
  `armor_p x defence_strength` (default 0.8, bounded to [0, 0.95]); the cost is `defence_upkeep x armor_p` per
  step (default 0.2), paid in the neutral arm `defence_neutral` too, which has no effect and draws nothing.
- The defaults come from a 30k-step pilot (3/4 runs met the world criteria) and were chosen by the owner after
  seeing it.
- **Save format v8**: each cell row gains `armor_p` as its 15th field; `counters` gains `defended`. v7 saves
  are rejected. The Rust loader reads v8, refuses `defence` on (until M5) and a nonzero `armor_p` with the flag off;
  the golden sets are regenerated, their hashes unchanged.
- **The extended-genome refactor is deferred to M5**, deviating from ADR-0010's trigger. The four propensities are
  four independent, flag-gated floats; the Rust kernel only checks that they are zero until M5, when it ports the
  flags. Restructuring them now would change the save layout and the Rust loader a second time for no experimental
  gain. M5 is the point where the record pays for itself.

## Consequences
- The default world is bit-identical (fingerprints on eight configurations; a test asserts no defence code runs).
- Predators have no answer to armour, so armour is expected to rise to its maximum. The result is about a world with
  less effective predation, not about an arms race.
- A fifth propensity, or M5, must do the refactor.
