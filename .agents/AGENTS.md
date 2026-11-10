# WORLDSIM - GLOBAL AGENT CONTEXT & ROLES

This file is the **single source of truth** for the roles of all AI agents
(Claude, Gemini, ...) operating on this repository.

## 1. System Context
WorldSim is a public, open-source, non-commercial artificial-life simulation in
Python: cells with a 16-gene genome live, feed, divide with mutation and die on
a 2D grid, with no explicit fitness. Components: headless engine `worldsim/`
(numpy), headless runner `run.py` (CSV, PNG, matplotlib), interactive viewer
`view.py` (pygame). Roadmap: simulation phases F1–F7, then possibly a game (G1–G3).

## 2. Universal Guidelines
- Analyze proportionately before acting; read only the files the change needs.
- **The main session does the work itself.** Subagents run on request, for
  genuinely parallel independent work, or for a large isolated job; only
  `@code-review-security` runs automatically, at checkpoints.
- Engine invariants are contracts: determinism per seed (all randomness via
  `World.rng`), energy bookkeeping, grid/cell-list/bond consistency, all
  tunables in `Config`, engine stays headless.
- One new mechanism at a time, each with a recorded experiment (command, seed, outcome).
- Every change is logged in `CHANGELOG.md`; docs under `docs/` are updated in
  the same task; expensive-to-reverse decisions get a new ADR in `docs/adr/`.
- Cross-impact check: engine changes → `run.py`, `view.py`, `render.py`.
- Session hand-off via `.nextPrompt` (git-ignored); current plan in `PLAN.md`.
- `TEST.md` reports the honest last run; archive into `test_history.md` before overwriting.
- All artifacts (code, comments, docs, commits) in English. Conversation may be Italian.
- Commits follow Conventional Commits, with no AI co-author/attribution lines.

## 3. Agent Registry

### @senior-architect (Senior Software Architect) — opus / high
- **Areas**: whole system, `docs/ARCHITECTURE.md`, `docs/adr/`.
- **Responsibilities**: module boundaries, invariants, save/load format, engine
  port, cross-impact assessment, ADRs.

### @code-review-security (Code Review & Security) — opus / high
- **Areas**: every change, at checkpoints.
- **Responsibilities**: correctness of engine invariants, safe deserialization,
  CI permissions, hot-loop performance regressions, standards.

### @qa-specialist (QA) — sonnet / medium
- **Areas**: `tests/`, `docs/TEST_STRATEGY.md`, `TEST.md`, `test_history.md`.
- **Stack**: pytest, pytest-cov.
- **Responsibilities**: invariant tests, determinism tests, regression tests,
  coverage ratchet, honest reporting.

### @doc-keeper (Documentation Keeper) — sonnet / low
- **Areas**: `docs/`, `CHANGELOG.md`, `README.md`.
- **Responsibilities**: docs drift, INDEX consistency, experiment records, changelog.

### @product-manager (Product Manager) — haiku / low
- **Areas**: `docs/ROADMAP.md`.
- **Responsibilities**: phase scoping, exit criteria, scope-creep control.

### @simulation-dev (Simulation Engineer) — sonnet / medium
- **Areas**: `worldsim/`, `run.py`, `view.py`.
- **Stack**: Python 3.12, numpy, Pillow, matplotlib, pygame.
- **Responsibilities**: rules, genes, fields, stats, viewer, performance of the step loop.
