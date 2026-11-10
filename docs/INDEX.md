# Documentation Index

Last updated: 2026-11-10

Welcome to the WorldSim technical and research documentation.

## Project and engineering

### [Roadmap](./ROADMAP.md)
Phases F1–F7 (simulation) and G1–G3 (game), status and exit criteria.

### [Architecture](./ARCHITECTURE.md)
Modules, the step loop, data flows and invariants.

### [Decision Records](./adr/)
Numbered, append-only records of the decisions that shaped the system:
[0001 ADRs](./adr/0001-record-architecture-decisions.md) ·
[0002 save format](./adr/0002-save-format.md) ·
[0003 species and novelty](./adr/0003-species-definition.md) ·
[0004 terrain and save v2](./adr/0004-terrain-and-save-v2.md).

### [Developer Guide](./DEVELOPER_GUIDE.md)
Bootstrap, running locally, tests, contribution rules.

### [Test Strategy](./TEST_STRATEGY.md)
What gets tested, at which level, and the coverage gate CI enforces.

### [Deployment Guide](./DEPLOYMENT_GUIDE.md)
CI pipeline and how the project is distributed.

## Research and design

### [State of the art](./state-of-the-art.md)
Survey of the Artificial Life field and options for WorldSim.

### [Theory](./theory.md)
Why WorldSim is not a genetic algorithm; the concepts at work.

### [Design v0](./design-v0.md)
Design of the current engine: world, genome, step cycle, tuning.
