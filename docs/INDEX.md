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
[0004 terrain and save v2](./adr/0004-terrain-and-save-v2.md) ·
[0005 sensor genes and save v3](./adr/0005-sensor-genes-and-save-v3.md) ·
[0006 rule genome and save v4](./adr/0006-rule-genome-and-save-v4.md) ·
[0007 two parents and save v5](./adr/0007-two-parents-and-save-v5.md) ·
[0008 engine port stack](./adr/0008-engine-port-stack.md).

### [G2 engine port plan](./G2_PLAN.md)
Milestones and verification criteria for the Rust core port (ADR-0008).

### [Developer Guide](./DEVELOPER_GUIDE.md)
Bootstrap, running locally, tests, contribution rules.

### [Test Strategy](./TEST_STRATEGY.md)
What gets tested, at which level, and the coverage gate CI enforces.

### [Deployment Guide](./DEPLOYMENT_GUIDE.md)
CI pipeline and how the project is distributed.

### [User Manual](./USER_MANUAL.md)
How to play *Planet in a jar*, use the viewer and runner, and make planets.

## Research and design

### [State of the art](./state-of-the-art.md)
Survey of the Artificial Life field and options for WorldSim.

### [Theory](./theory.md)
Why WorldSim is not a genetic algorithm; the concepts at work.

### [Design v0](./design-v0.md)
Design of the current engine: world, genome, step cycle, tuning.
