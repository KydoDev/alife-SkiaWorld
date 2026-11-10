# ADR-0002: World save format

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

## Context
F1 requires saving and reloading a world so that a resumed run continues
*exactly* like an uninterrupted one — otherwise experiments cannot be
reproduced or branched. Save files may be shared publicly (open-source project),
so loading one must never execute code. The state that drives the dynamics
includes more than the cells: the RNG state (with Python's cached Gaussian), the
order of `World.cells` (shuffled in place each step) and the iteration order of
each cell's `bonds` (energy sharing iterates them).

## Options considered
- **pickle** — trivial and complete, but loading an untrusted file can execute
  arbitrary code. Rejected for a public project.
- **numpy `.npz` (`allow_pickle=False`)** — safe and compact for arrays, but
  cells, bonds and the species tree are ragged structures that fit poorly.
- **gzip-compressed JSON with a format/version header** — safe, human-inspectable,
  floats round-trip exactly via Python's `repr`; larger and slower than binary.

## Decision
gzip-compressed JSON (`world_*.json.gz`), `{"format": "worldsim-save", "version": 1}`,
written by `worldsim/persistence.py`. Stored verbatim: config, seed, counters,
`next_id`, full `random.getstate()`, the organic field, cells **in list order**
with bond ids **in insertion order**, and the species tracker. `Cell.bonds`
became an insertion-ordered `dict` (used as an ordered set) because a `set`
rebuilt at load time cannot guarantee the original iteration order.
Loading validates format, version, config keys, grid bounds, tile collisions and
bond targets, and raises `SaveFormatError`.

## Consequences
- Resume is bit-exact: verified in tests at two split points and across
  processes (seed 1, 10k steps, resume at 5k → identical final save and stats).
- A save is ~280 KB at ~800 cells; fine for periodic saves, not for per-step replay.
- Any new state that affects the dynamics (new `Cell` slot, new field, new RNG
  use) must be added to the save and bump `VERSION`; old versions are rejected,
  not migrated, until there is a reason to migrate.
