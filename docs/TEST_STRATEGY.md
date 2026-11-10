# Test Strategy

Last updated: 2026-11-10

## Scope and philosophy
WorldSim is a scientific toy: the main risk is not a crash but a *silently wrong*
simulation — broken energy bookkeeping, ghost cells, or non-reproducible runs —
that makes every experimental conclusion worthless. Tests therefore target
engine invariants and reproducibility. Emergent behaviour (strategies, colonies)
is validated by recorded headless experiments, not by unit tests.

## Pyramid targets
| Level | Share | Framework | Runs |
|-------|-------|-----------|------|
| Unit (engine invariants on small seeded worlds) | ~80% | pytest | every PR |
| Integration (runner: `run.py` end to end, CSV/plot output) | ~15% | pytest + CI smoke run | every PR |
| E2E (viewer) | ~5% | manual | before a release |

The viewer (pygame) is checked manually; there is no user-facing release yet.

## Coverage gates
- Overall: 90% line coverage on `worldsim/` (currently ~98%), enforced in CI via `pyproject.toml`.
- Excluded: `worldsim/render.py` (pure visual mapping).
- Ratchet: the threshold may rise, never fall.

## Must-test list
- Grid ↔ cell list consistency (no duplicate, ghost or misplaced cells).
- Bond symmetry; bonds never point to dead cells; `max_bonds` respected.
- Determinism: same seed → identical stats history.
- Gene values stay in [0,1] after mutation.
- Energy bookkeeping (no energy created outside light) — *to add*.
- Organic matter never negative.
- Extinction → reseed.
- Columns of `stats()` that `run.py` reads by name.
- Every fixed bug: regression test first, failing.

## Test data
Small worlds (`40×20`, 80 cells), explicit seeds, ≤200 steps. No fixtures yet;
a saved-world fixture will come with F1 save/load.

## Known gaps
- No energy-conservation test yet (needs an accounting of light income per step).
- `run.py` and `view.py` have no automated tests beyond the CI smoke run.
