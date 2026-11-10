# The theory behind WorldSim

Last updated: 2026-11-10

> Why WorldSim is not a genetic algorithm, and which ideas from theoretical biology and ecology are at work inside the code.

## 1. The common root: the Darwinian algorithm

Dennett describes evolution as a substrate-independent **algorithm**. Lewontin's conditions state that evolution occurs wherever there is:

1. **variation**: individuals differ;
2. **heredity**: offspring resemble their parents;
3. **differential reproduction**: some variants leave more descendants.

In WorldSim these map to: a 9-number genome → copy with Gaussian mutation → energy decides who divides.

## 2. Genetic algorithm vs artificial life

| | Genetic algorithm (Holland) | Artificial life with implicit selection (Tierra, Avida, WorldSim) |
|---|---|---|
| Purpose | **Optimize**: find the best solution | **Explore**: see what emerges |
| Fitness | **Exogenous**: a function written by the programmer | **Endogenous**: whoever reproduces in that world, at that moment |
| Selection | External: candidates are ranked and the best are kept | Internal: you starve, get eaten, run out of space |
| Time | Synchronized generations | Overlapping births and deaths, continuously |
| World | Does not exist; there is only the score | It is everything: resources, space, other organisms |
| End | When the solution is found | Never, ideally |

Both belong to **evolutionary computation**. The precise name for WorldSim is an **evolutionary individual-based (agent-based) model**, within the field of Artificial Life.

## 3. Concepts at work in the system

### Dynamic adaptive landscape
In GAs the fitness landscape is fixed and evolution "climbs hills". In WorldSim the landscape is **built by the organisms**: many plants make predation pay off, many predators make something else pay off. This is **frequency-dependent selection**; in its extreme form it is the **Red Queen** (Van Valen): evolving continuously just to stay in place.

### Niches and trade-offs
**Competitive exclusion** (Gause): two species using the same resource do not coexist for long. In WorldSim there are three resources (light, organic matter, other cells) and the **trade-offs** are imposed by the exponent `p^spec_exp`: a generalist is mediocre at everything. Indeed, raising `spec_exp` from 1.5 to 2 made the strategies separate.

### Predator–prey
The plant/predator oscillations are the individual-based version of **Lotka–Volterra**. With spatially explicit individuals, effects emerge that the equations cannot see (e.g. bonded colonies that cannot be preyed upon from the inside).

### Thermodynamics
Life is a **dissipative structure** (Prigogine): order maintained by consuming a flow of energy. This is why energy is conserved in WorldSim: it enters only from light and leaves only through metabolism. Without a constrained flow there is no selective pressure.

### Evolution of evolvability
The mutation rate is a gene. Mutating a lot helps exploration but ruins the offspring of those already adapted; beyond the **error threshold** (Eigen) information degrades faster than selection can preserve it. In a stable environment faithful copiers win: this is what is observed in v0 (`mut` decreases). Prediction: in variable environments the rate should rise again.

### Major evolutionary transitions
Maynard Smith & Szathmáry: moments when independent replicators become parts of a higher-level unit (genes → chromosomes, cells → organisms, organisms → societies). The v0 colonies are the first step; the real leap requires **division of labor** among cells of the same organism.

### Emergence
No rule says "form colonies" or "stratify by depth": these behaviors are **emergent** from local rules + selection.

## 4. The open problem: open-ended evolution

Almost every simulation converges to an equilibrium and stops inventing; the biosphere does not. This is the central question of ALife (**open-ended evolution**).

- **How it is measured**: Bedau & Packard's *activity statistics* (innovations that appear and persist); the **MODES** metrics (change, novelty, complexity, ecology).
- **What would favor it** (hypotheses):
  - an environment that changes, including as an effect of the organisms themselves (niche construction);
  - **open genetic representation**: variable-length genome, rules or programs instead of a fixed vector;
  - rich interactions between organisms (coevolution, communication).

WorldSim v0 has a genome of 9 fixed numbers: the space of forms is **closed by construction**, so it cannot be open-ended. This is the natural direction for the next versions (see [`ROADMAP.md`](ROADMAP.md)).

## Reading list

- D. Dennett, *Darwin's Dangerous Idea*.
- J. Holland, *Adaptation in Natural and Artificial Systems* (the origin of GAs).
- T. Ray, *An approach to the synthesis of life* (Tierra, 1991).
- Lenski, Ofria, Pennock, Adami, *The evolutionary origin of complex features*, Nature 2003 (Avida).
- J. Maynard Smith, E. Szathmáry, *The Major Transitions in Evolution*.
- M. Bedau et al., *Open problems in artificial life*, Artificial Life 2000.
- T. Taylor et al., *Open-Ended Evolution: Perspectives from the OEE Workshop in York*, Artificial Life 2016.
- State of the art of existing projects: [`state-of-the-art.md`](state-of-the-art.md).
