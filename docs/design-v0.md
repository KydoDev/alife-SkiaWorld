# WorldSim v0 — Cells with genome and energy

Last updated: 2026-11-10

> v0 goal: a minimal 2D world in which **different life strategies emerge and coexist** without explicit fitness. Success = a stable ecosystem with at least 2 strategies (e.g. producers + predators/decomposers) after thousands of steps.

## Principles
- **Simple first, then layers.** No detailed physics: grid, energy, local rules.
- **No fitness.** Whoever reproduces survives; the only energy source is light.
- **Conserved energy.** Every joule comes from light and ends up in metabolism; the rest circulates (bodies → organic matter → decomposers).
- **Headless first.** Engine separate from the viewer (later portable to JAX/Rust/Unity).

## The world
- **W×H** grid (default 160×100). The x axis is toroidal (wraps around), y = depth: row 0 = surface, last row = seabed.
- **Light**: maximal at the surface, decays exponentially with depth **and** is shaded by every cell above (`shade^n`). → competition for light.
- **Organic matter**: a continuous field per tile. It comes from dead cells / undigested prey, **diffuses**, slowly **sinks** and decays.

## The cell
Occupies one tile. State: energy, age, genome, bonds with neighbors (colony).

### Genome (9 genes in [0,1], inherited with Gaussian mutation)
| # | Gene | Effect |
|---|---|---|
| 0 | `photo` | photosynthesis affinity |
| 1 | `sapro` | decomposition affinity (eats organic matter) |
| 2 | `pred` | predation affinity (eats neighboring cells) |
| 3 | `move` | probability of moving per step (only if not bonded) |
| 4 | `div` | energy threshold for dividing |
| 5 | `child` | fraction of energy given to the offspring |
| 6 | `attach` | probability that the offspring stays attached → colony |
| 7 | `share` | how much energy it shares with bonded cells |
| 8 | `mut` | mutation strength in the offspring (**the mutation rate evolves**) |

The three trophic genes are **normalized** (photo+sapro+pred = 1) and the gain uses `p^1.5`: specializing pays off, being a generalist costs. → a trade-off from which "plants", "fungi" and "predators" arise.

### Step cycle (random order across cells)
1. **Metabolism**: pays `base_cost + pred·pred_upkeep + move·move_upkeep` (having a mouth and muscles costs even when you don't use them).
2. **Photosynthesis**: `+ photo_gain · photo^1.5 · light(tile)`.
3. **Decomposition**: takes organic matter from the tile, `+ sapro_eff · intake`.
4. **Predation**: with probability `pred^1.5` attacks a neighbor **not bonded to itself**: gains `pred_eff ·` (energy + body) of the prey; the rest becomes organic matter.
5. **Movement**: if not bonded, with probability `move` moves to a free adjacent tile (at a cost).
6. **Sharing**: gives energy to poorer bonded cells (`share`).
7. **Division**: if energy ≥ threshold and there is a free tile: pays the **body cost**, the offspring receives `child` of the remaining energy and a mutated genome; with probability `attach` they stay bonded.
8. **Death**: energy ≤ 0 or maximum age → residual energy + body become organic matter.

## Immigration
Each step, on average 0.5 cells with a random genome appear in free tiles. Without immigration, "distant" niches (e.g. decomposers in the dark) are never reached, because the intermediate forms do not survive. It is a standard addition in ALife to maintain diversity; it can be turned off with `--set immigration_rate=0`.

## v0 tuning (values in `config.py`)
Grid 160×64 · 400 initial cells with energy 40 · `photo_gain` 3 · `spec_exp` 2 · `pred_eff` 0.5 · `organic_sink` 0.01 · `body_cost` 5 · `max_age` 600 · immigration 0.5/step.
First attempts: with `photo_gain` 1 the population collapsed; with `spec_exp` 1.5 plant–predator hybrids dominated; with sedimentation 0.05 organic matter immediately ended up on the seabed, out of reach.

## Observation
- **Colors**: green = photosynthesis, purple = decomposition, red = predation (mixed according to the genome). Background: blue = light, brown = organic matter.
- **Statistics** (CSV): population, count per dominant strategy, mean traits, % of cells in colonies, surviving lineages, total energy and organic matter.
- Periodic **PNG snapshots** + population chart.

## Out of scope for v0 (next layers)
1. Sensors + directional choices (moving towards food/light) → mini-brain.
2. Specialization within colonies (different cells in the same organism) → true multicellularity.
3. Chemical signals between cells → communication → basis for the social layer.
4. Seasons / day-night cycle, heterogeneous environments.
5. Phylogenetic tree and automatic identification of "species".
6. Port of the engine to JAX or Rust to scale to millions of cells.
