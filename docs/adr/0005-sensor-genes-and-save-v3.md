# ADR-0005: Sensor genes, per-gene species distance and save format v3

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

## Context
F3 gives cells perception and directed movement. Three choices are expensive to
reverse:

1. How behaviour is encoded: a small neural network, or a fixed set of weighted
   rules, and with how many genes.
2. Whether the new genes are always present or only when sensing is enabled.
3. What happens to the species definition (ADR-0003). It uses the Euclidean
   distance from the founder genome with an absolute threshold (0.3). That
   distance grows with the genome length, so appending genes would change what
   "a new species" means, and the F1 novelty metric with it. The roadmap uses
   that metric to decide when F4 starts.

## Options considered
- **Neural network** (inputs → hidden layer → move): more expressive, but 50+
  weights, slow in the Python hot loop, and hard to read back from `stats.csv`.
- **Weighted rules** (one weight per input, linear score per candidate tile):
  6 genes, each weight readable as "likes / dislikes X". This is level 1 of the
  roadmap's gene-growth plan.
- **Genes only when sensing is on**: no change to the off-world, but two genome
  lengths in one codebase, and saves that differ by a flag.
- **Genes always present**, unused when sensing is off: one genome, and a natural
  control arm in which the same genes drift neutrally.
- **Species distance**: keep the absolute threshold (it silently shrinks species),
  limit it to the first 10 genes (sensor genes would never define a species), or
  rescale the distance to a 10-gene genome.

## Decision
- Six sensor genes are appended at indices 10–15: `w_light`, `w_organic`,
  `w_chem`, `w_kin`, `w_stranger`, `w_danger`. Gene `g` maps to weight `2g − 1`.
- When `Config.sensing` is on, a moving cell scores staying put and each free
  neighbour tile as `sum(weight × input) + sense_noise × U(0,1)` and goes to the
  best one. The inputs are light (÷ `light_max`), organic matter and chemical
  energy (each saturating as `v / (v + 1)`), plus the densities of kin (same
  lineage, never the tracker's species), strangers and danger (the predator
  share of all of them, kin included, because predation does not spare kin)
  among the mover's neighbours that touch that tile. Densities are divided by
  the number of those neighbour tiles that exist, so the surface and floor rows
  are not understated.
  Perception radius is 1. Staying costs nothing, so a mover can also choose to stay.
- Sensing costs `sense_upkeep × mean |weight|` per step, so the weights are not
  free to grow.
- `sensing` is **off by default**. The genes are always present and inert when
  it is off: the same seed gives the same history whatever their values (tested).
- The species distance is rescaled: `genome_distance = dist × sqrt(10 / n_genes)`.
  The threshold keeps its per-gene meaning from F1/F2.
- **Save format v3**: same layout as v2, with 16-gene genomes. v2 saves are
  rejected with a clear message.

## Consequences
- As with F2, appending genes changed every seed's random stream. F2 numbers
  reproduce only at the F2 commit, and the F3 comparisons are on/off within the
  new engine.
- Sensing costs about 30% of the speed (≈ 545 → 380 steps/s, seed 1, 3000 steps;
  563 before F3). The off-world loses only noise. An earlier 438 steps/s figure was
  measured at a faster moment of the machine: the pre-review code gave 397 in the
  same session as the 380.
- Hunting can barely emerge: predation already strikes any adjacent cell, and
  perception has radius 1. A wider radius is a later, separate experiment.
- Known asymmetries of the control arm, accepted and to keep in mind when reading
  the F3 experiment:
  - A sensing cell that passed the movement gate may still choose to stay, so
    with zero weights it moves somewhat less often than a random walker.
  - `sense_upkeep` is paid by every cell, including bonded or immobile ones that
    never use their senses, as `move_upkeep` is. Colonies pay a small extra cost
    only in the sensing arm.
  - The rescaled species distance keeps its per-gene meaning only when all genes
    drift alike. With sensing off the six sensor genes drift neutrally and add to
    the distance, while divergence in the ten trait genes counts about 0.79× as
    much as before. Novelty is comparable between F1/F2 and F3 in order of
    magnitude, not exactly.
- Saves are checked against the species tracker (founder genome length and
  values, every cell's species extant), so a stale or hostile save fails on load
  rather than at the first birth.
- A network-based brain (and learning, ROADMAP "after F3") can replace the linear
  score later behind the same `sensed_move` entry point.
