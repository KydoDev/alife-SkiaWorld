# WorldSim — Roadmap

Last updated: 2026-11-10

> How to grow WorldSim from a "cell ecosystem" into something open-ended, and possibly into a game.
> Guiding rule: **one new mechanism at a time**, each with an experiment that tells whether it worked. The order of phases 3–7 is flexible.

## Overview

```
SIMULATION (lab, Python)                          GAME (product)
F1 Foundations ──► F2 Living environment + world seed ──► G1 "Planet in a jar" prototype
                   F3 Sensors and behavior                 G2 Engine port (C#/Burst or Rust)
                   F4 Open genome                          G3 Goals, progression, UI
                   F5 Two parents and plasticity
                   F6 True multicellularity
                   F7 Signals → social
```

---

## v0 — Base engine
**Status**: done (2026-11). Cells with a 9-gene genome, energy, light, organic matter, colonies; headless runner and pygame viewer. See [design-v0.md](design-v0.md).

## F1 — Foundations (before adding biology)
**Status**: in progress — regression test suite started (2026-11-10); it revealed that determinism per seed is currently broken (see `TEST.md`).

Without these tools you cannot tell what is going on as the system grows.
- **Saving/loading** the world and **determinism** (same seed → same history).
- **Species tracking**: genome clustering + phylogenetic tree (who descends from whom).
- **Novelty metrics** (Bedau activity statistics) to measure whether the system is still inventing or has stalled.
- Regression tests (energy conservation, no duplicated cells in the grid).
- Profiling: currently ~500 steps/s with ~900 cells. Practical Python limit ≈ a few thousand cells.

**Exit criterion**: I can re-run a simulation, see its species tree and a "novelty over time" chart.

## F2 — Living environment + world seed
**Status**: planned

- Day/night cycle and **seasons** (variable light).
- Heterogeneous terrain: rocks, mineral-rich zones, hydrothermal vents (chemical energy, not just light).
- **World generated from an input** (photo or form, see the dedicated section).
- Experiment: in a variable environment, does the mutation rate rise again? Do seasonal strategies (spores, reserves) arise?

## F3 — Sensors and behavior
**Status**: planned

- The cell perceives its 8 neighboring tiles: light, organic matter, presence of cells, kinship.
- **Directed** movement (towards food/light, away from predators) instead of random.
- Implementation: a small neural network or a set of weighted rules, **with the weights in the genome**.
- Experiment: do hunting, fleeing, day/night vertical migrations emerge?

## F4 — Open genome (growing the number of genes)
**Status**: planned

See the dedicated section. In short: from a fixed vector to a **variable-length genome** with gene duplication and deletion.

## F5 — Two parents and variation during life
**Status**: planned

See the dedicated section: sexual reproduction, plasticity, learning, horizontal gene transfer.

## F6 — True multicellularity
**Status**: planned

- Cells of the same colony can **differentiate**: same genome, different expression depending on position or signals (like the cells of an embryo).
- Organism = colony with a "developmental plan"; reproduction via propagule or spore.
- Experiment: do organisms with specialized parts appear (leaves that photosynthesize, roots that absorb, "mouths")?

## F7 — Signals and social
**Status**: planned

- Chemical signals emitted and perceived (channels in the field, like organic matter).
- Kin recognition, cooperation, altruism towards relatives (kin selection), alarm signals.
- Beyond that: groups, territories, resource exchange → bridge towards social simulation (Sugarscape).

---

## When to increase the number of genes?

Today each gene is **hand-wired to a trait** (gene 3 = movement, etc.). Three levels can be distinguished:

1. **Adding fixed genes**: done **every time a mechanism is added** (F2–F3). Example: sensors bring ~10–30 extra weights. It is simple and can be done right away, but the space stays closed: evolution can only turn knobs I have anticipated.
2. **Variable-length genome** (F4): the genome becomes a list of "genes" (e.g. rules *if I perceive X then I do Y with intensity Z*). Mutations can **duplicate** a gene (the copy is free to evolve towards a new function: this is the main mechanism by which new functions arose in nature), **delete** it or modify it. This way the number of genes is decided by evolution.
3. **Regulatory network**: genes switch each other on and off. This is the prerequisite for the cellular differentiation of F6.

**When to move to level 2**: when F3 works and the F1 novelty metrics show that the system stabilizes. The clear signal is that the system "stalls" even in a variable environment.
**Cost**: more genes mean more computation per cell and more often harmful mutations. This must be balanced with a **metabolic cost per gene**, otherwise genomes bloat for no reason.

## Variation of parents over time

There are four distinct mechanisms, in order of difficulty:

| Mechanism | What changes | Expected effect | Phase |
|---|---|---|---|
| **Two parents** (sexual reproduction) | The offspring combines the genomes of two cells (crossover) | Combines innovations that arose in different lineages, purges harmful mutations; requires finding a partner (sexual selection!) | F5 |
| **Plasticity / epigenetics** | During life some traits adjust to the environment (e.g. more photosynthesis if there is light), without changing the DNA; part of this can pass to the offspring | Fast adaptation without waiting for mutations | F5 |
| **Learning** | The "brain" (F3) modifies its weights during life | Baldwin effect: what is easily learned tends to later become innate | after F3 |
| **Horizontal transfer** | A cell absorbs pieces of genome from neighbors or from organic matter | Like bacteria: rapid spread of innovations across lineages | F5 |

**Lamarckism** (the parent changes its own genome during life and passes it to its offspring): can be done with a flag, and is an interesting experiment to compare against the Darwinian version.

---

## World seed from a photo or form

The seed is not genetic: it is the **planet**. The input generates the environment; life always starts from random cells and adapts to that world. The result is that **every photo becomes a different world with a different evolutionary history**.

### From a photo
- The image is resized to the grid.
- **Brightness → light / altitude**: bright areas = illuminated surface, dark areas = depth.
- **Color → resources**: e.g. red channel = minerals/heat (chemical energy), blue channel = water/nutrients, green channel = initial fertility.
- **Strong edges → rocks/barriers**: they separate populations, so different species arise in different areas (geographic speciation).
- **Image hash → random seed**: same photo = same world, reproducible and shareable.

### From a form ("create your planet")
Each form field becomes a parameter of `Config` or of terrain generation:
- star type → intensity and color of the light, length of day and year;
- temperature and seasonality;
- ocean depth, amount of emerged land;
- mineral richness, volcanic activity (chemical energy sources);
- **"chemistry of life"**: carbon / silicon / ammonia / … as rule *presets*. E.g. silicon life is slow, sturdy, and lives on heat instead of light. This brings back the original idea of alternative elements, but as **different rules of the world**, which is where it really matters.
- difficulty: frequency of catastrophes (meteorites, ice ages).

**Implementation**: it is entirely an addition within F2. A `worldgen` module is written that produces the maps (light, resources, rocks) and the `Config` from an image or a JSON file. The engine does not change.

---

## Turning it into a game

### Existing references
SimLife (Maxis, 1992), Spore (2008), *Species: Artificial Life, Real Evolution*, *Thrive* (open source), Equilinox, The Bibites. The genre exists but is niche. Those who succeeded gave the player **clear verbs**, not just a screen to watch.

### The main risk
An ALife simulation is fascinating to watch for 10 minutes and then gets boring. It needs a **game loop**: *what does the player do, every minute?*

### Proposed concept: "planet in a jar" (god game sandbox)
- **Creation**: the player generates the planet from a photo or from the form.
- **Observation**: watches life emerge, inspects species, names them; a tree of life is visible.
- **Intervention** (player verbs, with a budget of "divine energy"): move light or nutrients, dig channels, raise mountains (separate populations), meteorites and ice ages, introduce a species from another planet.
- **Goals / milestones**: "first multicellular organism", "first predator", "10 coexisting species", "survive a mass extinction", "evolve communication". Challenge mode: "on this hostile planet, achieve X within N generations".
- **Sharing**: a planet = photo + form, so it is easy to share; different evolutionary histories from the same seed can be compared.

### Architecture
- **The engine stays separate, deterministic and headless**: the game is a front-end.
- Python remains the **lab** for trying out rules.
- The game needs an **engine port**, because Python cannot handle tens of thousands of cells at 60 fps. Two options:
  1. **Unity + C# with Jobs/Burst** (or compute shaders): a single stack, the most practical route.
  2. **Rust** as a native library called from Unity: higher performance and reusable, but with two languages to maintain.
- The right time for the port: **after F3**, when the basic rules are stable; porting earlier means rewriting twice.

### Game phases
- **G1 (after F2)**: playable prototype in Python/pygame. Photo or form → planet, 3–4 interventions, 5 milestones. Check whether it is fun **before** investing in the port.
  - **Status**: planned
  - Deliverable: docs/USER_MANUAL.md (user manual for the viewer/game)
- **G2 (after F3)**: engine port and visualization in Unity.
  - **Status**: planned
- **G3**: UI, tree of life, progression, saves, sharing.
  - **Status**: planned
