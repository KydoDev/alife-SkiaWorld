# ADR-0010: Horizontal gene transfer and save format v7

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

## Context
F5c is the third of the four F5 mechanisms. The roadmap describes it as "a cell absorbs pieces of genome from
neighbors or from organic matter, like bacteria: rapid spread of innovations across lineages". The guiding rule
is still one mechanism at a time. G2 runs in parallel (`docs/G2_PLAN.md`, "Parallel work with the F-phases"),
so the default world must stay bit-identical and any save change must be cheap for the Rust loader.

The choices below are expensive to reverse:
1. **Where the genes come from**: living neighbours or dead cells' remains.
2. **What moves**: how much genome, and whether it changes the recipient for life.
3. **Whether transfer is imposed or evolvable**, and how it is stored.
4. **What makes it costly**, so that it does not win by construction.

## Options considered
- **Source**:
  - living Moore neighbours (conjugation-like). This needs no new field;
  - a gene pool carried by organic matter (transformation). This needs a per-tile genetic field that diffuses
    and sinks with the organic matter: a large addition to the save and to the port.
- **Unit**: one locus of the 16 fixed genes; a block of loci; rule genes too.
- **Timing**: during life, where the recipient's genome changes and is inherited; or only at division, which
  would be one-locus sex and duplicates F5a.
- **Filter**: none (any lineage), or a genetic-distance limit like F5a mating. A limit would remove the
  cross-lineage character that distinguishes transfer from sex.

## Decision
- **Neighbour donors, one fixed locus, during life.** With `Config.hgt` on, at the start of its turn (before
  feeding) a cell transfers with probability `hgt_p x hgt_rate`:
  - it picks a random occupied Moore neighbour (bonded or not, any lineage) and a random locus among the 16
    fixed genes;
  - it copies the donor's value. The donor is unchanged;
  - the recipient gets a new gene list and is re-expressed.

  Rule genes, `sex_p`, `plast_p` and `hgt_p` itself are never transferred.
- **Re-expression.** `express()` recomputes every derived trait. With plasticity on, it also resets the
  acclimated diet to the new genetic split, which keeps the loader's frozen-diet check valid. Species labels
  stay as assigned at birth: the tracker is not told, because it is a pure observer and is defined at birth.
- **Evolvable propensity `hgt_p`** in [0, 1], stored outside the genome like `sex_p` and `plast_p`:
  - seeded cells and immigrants draw it at random, after the `plast_p` draw;
  - children inherit the dividing parent's, mutated with its `mut_sigma`;
  - it exists and draws random numbers only when the feature is on.
- **Cost.** `hgt_upkeep x hgt_p` per step (default 0.05), paid in the neutral arm `hgt_neutral` too. That arm
  inherits and mutates `hgt_p` but never transfers and draws nothing for it.
- **Rate.** The default `hgt_rate` is 0.1. A probe found a mean lifespan of about 17 steps, so at `hgt_p` 0.5
  this gives about one transfer per birth.
- **Save format v7.**
  - Each cell row gains `hgt_p` as its 14th field (finite, in [0, 1], 0 when the feature is off).
  - `counters` gains `hgt_events` and `hgt_foreign`, the transfers whose donor is of another lineage.
  - v6 saves are rejected.
  - The G2 golden sets were regenerated in the same change, and `hashes.csv` is unchanged. The Rust
    `SAVE_VERSION` is 7. The G2 state-hash definition is unchanged, since the new counters are 0 in the
    default world and are not part of it.

## Consequences
- The off-world is bit-identical to `367aecd`. Full-state fingerprints match on six configurations: default,
  day/night + sensing, F4, F5a, vents + rock, and F5b plasticity on. A test asserts that no transfer code runs
  when the feature is off.
- Speed: off, no measurable change (≈ 540–560 steps/s, noise ±20). On, about 5% slower.
- The probe found that with immigration 0, neighbours are near-clones: the median gene difference at a locus is
  about one mutation step, and 0–9% of donors are of another lineage. In this world a transfer is mostly an
  extra small mutation, so the experiment's null is worded as "mechanism nearly inert here".
- Limit: with plasticity on, every transfer resets the acclimated diet, even when the copied locus is not a
  feeding gene or the donor's value is equal. In a combined F5b + F5c run, lost acclimation is part of the
  cost of transfer, so such a run would confound the two mechanisms. The F5c experiment runs with plasticity
  off. A combined experiment should first re-express only the derived traits and keep the diet unless a
  feeding gene changed.
- The loader also rejects `hgt_foreign > hgt_events`.
- Transfer from organic matter, a distance-filtered transfer, and transfer of rule genes are later, separate
  experiments.
- `sex_p`, `plast_p` and `hgt_p` are three per-cell values outside the genome. ADR-0009 already noted that a
  small "extended genome" record would be cleaner. A fourth such value should trigger that refactor, together
  with the Rust loader.
