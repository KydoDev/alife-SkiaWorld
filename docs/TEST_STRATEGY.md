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
- F2 environment: light cycles mean-preserving and bit-exact on resume mid-cycle; no cell
  ever on rock; terrain RNG independent of `World.rng`; custom terrain survives save/load.
- Untrusted input (planet forms, images, saves): every rejection path from the security
  review has a regression test (ranges, sizes, formats, gzip bombs, hostile values).
- Energy bookkeeping: closed system (all sources/sinks off) conserves total energy.
- Organic matter never negative.
- Extinction → reseed.
- Save/load: resume from file is bit-exact vs. an uninterrupted run (two split
  points, per-cell comparison incl. bond order); invalid files are rejected.
- Species tracker is a pure observer (identical history with tracking on/off and
  with different thresholds); species counts match living cells; ancestry intact
  after pruning; novelty counts only speciation-born species.
- Columns of `stats()` that `run.py` reads by name.
- Every fixed bug: regression test first, failing.

## Test data
Small worlds (`40×20`, 80 cells), explicit seeds, ≤300 steps; `tmp_path` for save files. No fixtures yet;
a saved-world fixture will come with F1 save/load.

## Known gaps
- Energy accounting with sources/sinks on (light income vs upkeep) is not tested; only the closed system is.
- `run.py`, `plots.py` and `view.py` have no automated tests beyond the CI smoke runs
  (headless run + resume). Charts are checked by eye.
