# ADR-0009: Within-life diet plasticity and save format v6

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

(ADR-0008, the G2 engine port, was decided in a parallel branch.)

## Context
F5b is the second of the four F5 mechanisms, and the roadmap describes it as "during life some traits adjust to
the environment (e.g. more photosynthesis if there is light), without changing the DNA". The guiding rule is
still one mechanism at a time. The choices below are expensive to reverse:

1. **Which trait is plastic, and what drives it.**
2. **Whether plasticity is imposed or evolvable, and how it is stored.**
3. **Whether the acquired state passes to the offspring.**
4. **What makes plasticity costly**, so that it does not win by construction.
5. **Keeping the default world unchanged**, and with it the G1 calibration.

## Options considered
- **Plastic trait**:
  - the diet split (photo / sapro / chemo), which is the roadmap's own example;
  - the division threshold;
  - sensor weights. The F4 rules already make these conditional on state, so making them plastic again would
    duplicate F4.
- **Driver**:
  - the cell's own energy gains, which need a history buffer;
  - what each diet would yield on its own tile right now. This is local, needs no memory, and the loop already
    reads it.
- **Storage**:
  - a 17th gene, which shifts every seed's random stream (as F2 and F3 did) and forces a recalibration of G1;
  - a per-cell value that exists only when the feature is on, as F5a `sex_p` and the F4 rules do.
- **Inheritance of the acquired diet**:
  - none (Darwinian);
  - partial (epigenetic);
  - full (Lamarckian).

## Decision
- **Trait and storage.** With `Config.plasticity` on, each cell has `plast_p` in [0, 1], its acclimation rate.
  - Seeded cells and immigrants draw it at random.
  - Children inherit it from the dividing parent only, mutated with its `mut_sigma`.
  - It is not a gene: like `sex_p`, it exists and draws random numbers only when the feature is on.
- **The diet.** The predation share stays genetic. The non-predatory share is split by an acclimated `diet`,
  three proportions.
  - At birth the diet is the genetic split. The acquired diet is **not inherited**: epigenetic and Lamarckian
    inheritance are later, separate experiments.
- **The update.** Each step, before feeding, the cell computes what each diet would yield on its tile at full
  specialisation and moves `diet += plast_p x plastic_rate x (t - diet)`, where `t` is those yields as
  proportions.
  - No RNG; with nothing to gain on the tile, the diet does not move.
  - The default `plastic_rate` of 0.05 gives a lag of at least 20 steps, against a 200-step day and a lifespan
    of up to 600 steps.
  - The update tracks proportional yields, not the single best diet. With `spec_exp` > 1 a full switch would
    pay more, so this is a deliberately bounded, lagged response.
- **Cost.** `plastic_upkeep x plast_p` per step (default 0.05). It is paid in the neutral arm too, so a neutral
  arm with a high cost is a pure-cost positive control, and a neutral arm with cost 0 is the drift baseline.
- **Phenotype derivation.** When plasticity is on, the phenotype shares are always derived from the diet, at
  birth too. A resumed world therefore computes the same floats as an uninterrupted one.
- **Save format v6.** Each cell row gains `plast_p` (finite, in [0, 1], 0 when the feature is off) and `diet`
  (3 proportions summing to 1, empty when off). v5 saves are rejected.

## Consequences
- The off-world is bit-identical to the P1 commit `c3e1c43`. Full-state fingerprints were checked locally on
  five configurations: default, day/night + sensing, F4, F5a, and vents + rock. A test asserts that no
  plasticity code runs when the feature is off. Speed off is unchanged (~580 steps/s); on, it drops to
  ~400 steps/s.
- The strategy counts, the render colours and the inspector all read the plastic phenotype, so a cell can
  change colour during its life.
- Species are still defined on genes. Plasticity can buffer selection on the diet genes, so species counts may
  change without any change in what cells can do. Compare species between arms with care.
- `plast_p` and `sex_p` are both kept outside the genome. If more such values appear, a small "extended
  genome" record would be cleaner than more cell slots.
