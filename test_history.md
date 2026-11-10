# Test history

Archive of previous `TEST.md` reports, newest last, each under a dated separator.

---
## Archived 2026-11-10 (before determinism fix)

# Test Report

Last run: 2026-11-10 — working tree on top of `d1d8e9c` (governance setup)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit (`tests/test_world.py`) | 11 | 0 | 1 xfail | 98% (`worldsim/`, excl. render) |
| Integration (CI smoke run) | not yet run in CI | | | |
| E2E (viewer, manual) | not run | | | |

Lint: `ruff check .` — clean.

## Failures
### `test_same_seed_gives_identical_history` — xfail (strict), known bug
- **Error**: two `World(cfg, seed=11)` instances diverge at step ~4.
- **Suspected cause**: `Cell.bonds` is a `set` of `Cell` objects hashed by `id()`;
  iteration order in the energy-sharing step varies between runs, changing float
  results once colonies form.
- **Task**: added to `.nextPrompt` (fix determinism, then remove the xfail).

---
## Archived 2026-11-10 (before F1)

# Test Report

Last run: 2026-11-10 — after `fix(engine): make runs deterministic per seed`

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit (`tests/test_world.py`) | 12 | 0 | 0 | 98% (`worldsim/`, excl. render) |
| Integration (headless run, seed 1, 1000 steps, two processes) | `stats.csv` byte-identical | | | |
| E2E (viewer, manual) | not run | | | |

Lint: `ruff check .` — clean.

## Failures
None.

---
## Archived 2026-11-10 (before the F2 commit)

# Test Report

Last run: 2026-11-10 — F1 Foundations (working tree before the F1 commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 27 tests) | 27 | 0 | 0 | 98.7% (`worldsim/`, excl. render) |
| Exit demo: seed 1, 10k steps vs resume at 5k (separate processes) | final saves identical, 500/500 stats rows identical | | | |
| Observer purity: 3000-step run with tracker vs pre-tracker baseline | 300/300 rows identical on existing columns | | | |
| E2E (viewer, headless screenshot incl. `--load`) | renders, panel complete | | | |

Lint: `ruff check .` — clean.

## Failures
None.
