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

---
## Archived 2026-11-10 (before the G1 commit)

# Test Report

Last run: 2026-11-10 — F2 Living environment + world seed (working tree before the F2 commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 80 tests) | 80 | 0 | 0 | 98.3% (`worldsim/`, excl. render) |
| Defaults-off light cycle vs F2 baseline (seed 1, 2000 steps, before the gene change) | 200/200 stats rows identical | | | |
| CI smoke commands (run, resume, form planet, image planet, resume of an image planet) | all complete | | | |
| Viewer (headless, `--planet examples/volcanic.json`, 5 frames + screenshot) | renders, panel complete | | | |
| Perf back-to-back, seed 1, 3k steps: F1 commit vs F2 tree | 303 vs 354 steps/s (no regression) | | | |

Lint: `ruff check .` — clean.

## Failures
None.


---

<!-- archived 2026-11-10 -->

# Test Report

Last run: 2026-11-10 — G1 "Planet in a jar" prototype (working tree before the G1 commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 99 tests) | 99 | 0 | 0 | 98.7% (`worldsim/`, excl. render) |
| Idle-player control: no interventions, 6000 steps (default, volcanic, red_dwarf, planet.png, default seed 7) | 0 milestones on every planet | | | |
| Scripted player, `examples/volcanic.json` | 4/5 milestones; survivors verified with an aimed shower (step 5240) | | | |
| Scripted player, default / red_dwarf / planet.png | 1–3 of 5 (documented as harder planets) | | | |
| Game (headless pygame, scripted clicks: volcano, meteorite, mountain drag, inspect) | renders, panel and toasts complete | | | |

Lint: `ruff check .` — clean.
Not covered by tests: whether the game is fun (owner playtest = G1 exit criterion).

## Failures
None.
