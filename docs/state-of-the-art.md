# WorldSim — State of the art (Artificial Life)

Last updated: 2026-11-10

> Initial research, 10 November 2026. A survey of existing projects that simulate and evolve life-like systems, grouped by approach, to decide WorldSim's direction.

## The field in brief

The field is called **Artificial Life (ALife)**. It has an academic community (International Society for Artificial Life, annual ALIFE conference) and a very active indie/hobbyist scene.

The central problem of the field is **open-ended evolution (OEE)**: almost every simulation produces novelty for a while and then settles down. No system has yet convincingly made the jump from "cell" to "complex organism". This is where the open questions are, and also where it is easiest to get lost.

---

## 1. Digital organisms (code is the DNA)

The "organisms" are programs that self-replicate, mutate and compete for computing resources. There is no chemistry: the substrate is the code.

| Project | Year | Notes | Links |
|---|---|---|---|
| **Tierra** (Thomas Ray) | 1991 | The progenitor. Programs written in a virtual assembly language compete for CPU time; parasites and hyperparasites arise. | — |
| **Avida** (Ofria, Lenski, Adami) | 1993→ | The scientific successor to Tierra. Used for real studies in evolutionary biology (Nature 2003, origin of complex features). There is also Avida-ED, the educational version. | [github.com/devosoft/avida](https://github.com/devosoft/avida) · [Wikipedia](https://en.wikipedia.org/wiki/Avida_(software)) · [Avida-ED](https://avida-ed.github.io/) |
| **Computational Life / BFF** (Google) | 2024 | A "soup" of random programs in a Brainfuck-like language: with no explicit fitness at all, self-replicators emerge **spontaneously**. A key result on the origin of life. | [arXiv 2406.19108](https://arxiv.org/abs/2406.19108) · [Google Research](https://research.google/pubs/computational-life-how-well-formed-self-replicating-programs-emerge-from-simple-interaction/) |

**Pros**: fast, the results are measurable, and it takes little code. **Cons**: not very visual, and far from the idea of a "creature".

---

## 2. Artificial chemistries and physics (life emerges from the rules)

This is the "from the cell up" path. You define the "elements" and the interaction rules, and watch whether structures emerge that maintain and replicate themselves. **This is where the idea of non-carbon-based life fits in**: with an invented chemistry, you define the elements yourself.

| Project | Year | Notes | Links |
|---|---|---|---|
| **Lenia** (Bert Chan) | 2019 | Continuous cellular automaton (a Game of Life with continuous values, space and time). Hundreds of "species" arise that move and divide. Can be implemented in little code. | — |
| **Flow-Lenia** | 2022/2025 | Adds mass conservation and local parameters (the "genome" travels with the creature). Allows evolution and competition between species in the same world. | [Website](https://sites.google.com/view/flow-lenia) · [arXiv 2212.07906](https://arxiv.org/abs/2212.07906) · [arXiv 2506.08569](https://arxiv.org/abs/2506.08569v1) |
| **ALIEN** (Christian Heinemann) | 2020→ | CUDA/GPU particle engine: particles joined by bonds, with specialized cells (sensors, muscles, nerves). Evolves multicellular organisms. Open source and among the most mature projects. | [alien-project.org](https://alien-project.org) · [github.com/chrxh/alien](https://github.com/chrxh/alien) · [itch.io](https://chrxh.itch.io/alien) |
| **Particle Life** | 2010s→ | N particle types with an attraction/repulsion matrix: cell-like structures arise from minimal rules. "Evolutionary" versions exist. | [tom-mohr/particle-life](https://awesome.ecosyste.ms/projects/github.com%2Ftom-mohr%2Fparticle-life) · [Evolving Particle Life](https://quasarbright.github.io/evolving-particle-life/) |
| **Microcosmos** | 2026 | GPU ALife engine in JAX: organisms made of elastic filaments in a 2D fluid (Lattice Boltzmann + Position-Based Dynamics). Reaches 500k particles on a single GPU and is differentiable. Authors: Chan, Stanley and others. | [arXiv 2607.02954](https://www.alphaxiv.org/abs/2607.02954) |
| **Artificial chemistries** (Hutton; Kruszewski & Mikolov) | 2002, 2020 | Abstract molecules and reactions from which self-replicators and autocatalytic metabolisms emerge. | [Hutton – replicating molecules](https://faculty.cc.gatech.edu/~turk/bio_sim/articles/hutton_rep_molecules.pdf) · [Combinatory Chemistry](https://arxiv.org/abs/2003.07916) · [Self-reproducing metabolisms](https://arxiv.org/abs/2103.08245) |

**Pros**: the most "genuine" line of work and the most spectacular to watch. **Cons**: computationally expensive, and often nothing evolves beyond simple forms.

---

## 3. Agents with brains, and ecosystems

Creatures have a genome that encodes body and neural network; they live in a world with food and energy, and they reproduce and die. Behavior evolves.

| Project | Year | Notes | Links |
|---|---|---|---|
| **Polyworld** (Larry Yaeger) | 1994 | The academic classic: 3D agents with neural networks, vision, mating and fighting. | [shinyverse.org/larryy/PolyWorld](https://shinyverse.org/larryy/PolyWorld.html) |
| **The Bibites** | 2020→ | A very polished indie simulator (built in Unity): genome + evolvable neural network, hormones, predation. An excellent reference for UX and game design. | [itch.io](https://thebibites.itch.io/the-bibites) · [Website](https://thebibites-website.pages.dev/) |
| **JaxLife** (Oxford) | 2024 | Agents with neural networks in a world with resources, terraforming and programmable "robots", designed for open-ended evolution and the emergence of social and cultural behavior. Written in JAX. | [arXiv 2409.00853](https://arxiv.org/html/2409.00853v1) |

---

## 4. Social simulation (Agent-Based Modeling)

Bodies do not evolve: strategies, exchanges, norms and cultures do.

| Project | Notes | Links |
|---|---|---|
| **Sugarscape** (Epstein & Axtell, 1996) | The reference model: agents on a resource map, with trade, migration, culture and conflict. | — |
| **NetLogo** | Classic ABM environment, with a huge library of models (Sugarscape included). | — |
| **Mesa** | ABM framework in Python, the most widely used today. | [mesa.readthedocs.io](https://mesa.readthedocs.io/) · [PyPI](https://pypi.org/project/mesa) |

---

## 5. Recent tools and methods to keep an eye on

- **ASAL — Automating the Search for Artificial Life** (Sakana AI + MIT and others, 2024): uses vision-language foundation models (CLIP etc.) to **automatically search** the parameter space of Lenia, Particle Life, Boids and others for simulations that produce interesting or "open-ended" behavior. It solves the "I have a thousand parameters, which ones do I try?" problem. [sakana.ai/asal](https://sakana.ai/asal/) · [arXiv 2412.17799](https://arxiv.org/abs/2412.17799)
- **Directing OEE via multi-scale path divergence** (2026): metrics to steer and measure open-ended evolution. [astrobiology.com](https://astrobiology.com/2026/06/directing-open-ended-evolution-in-artificial-life-via-multi-scale-path-divergence.html)
- **General trend**: everything is moving to **GPU + JAX** (Microcosmos, JaxLife, ASAL, Flow-Lenia in JAX), with millions of entities and differentiability.

---

## How they are usually built

Almost every project has the same 4 layers:

1. **Substrate / physics**: grid, particles or fluid, with interaction rules and energy.
2. **Genome → phenotype**: how heritable information builds body and behavior.
3. **Implicit selection**: no explicit fitness. There are scarce resources, energy costs and death, and whoever reproduces survives.
4. **Observation**: visualization, diversity metrics, phylogenetic trees, saving and replay.

Typical architecture: a **headless simulation engine** (C++/CUDA, Rust or Python+JAX) separate from the **viewer** (web, Unity or a native GUI).

---

## Options for WorldSim (to be decided)

| Option | What emerges | Difficulty | References |
|---|---|---|---|
| **A. Artificial chemistry** with invented elements (e.g. "non-carbon") | Self-replicators, protocells | High, uncertain results | Hutton, BFF, Flow-Lenia |
| **B. 2D cells with a genome** (one level above chemistry) | Organisms, multicellularity, ecosystems | Medium | ALIEN, Bibites, Microcosmos |
| **C. Agent ecosystem** with neural networks | Behaviors, predation, cooperation | Medium | Polyworld, JaxLife |
| **D. Social (ABM)** | Economy, culture, norms | Low-medium | Sugarscape, Mesa |

**Initial recommendation**: start from **B**, with simple physics and a small genome, get it running early, then add layers. Communication and social behavior (C → D) become later phases of the same world, not alternative projects. Option A only makes sense if the goal is specifically to study the origin of life, because the risk of "nothing happens" is high.
