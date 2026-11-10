# Test Report

Last run: 2026-11-10 — F3 Sensors and behavior (F3 commit, after the code review fixes)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 118 tests; new `tests/test_sensing.py`) | 118 | 0 | 0 | 98.6% (`worldsim/`, excl. render) |
| F3 experiment (`scripts/f3_experiment.py`, 16 arms x 10k steps) | descendants only: phototaxis likely selected (immigration arms: mean w_light +0.26 on vs −0.16 off, 2 seeds); no fleeing, hunting or consistent day/night migration; sensing-off arms match the pre-review run on all columns | | | |
| G1 idle-player control after F3 (6000 steps; default, volcanic, red_dwarf, planet.png) | 0 milestones on every planet (after the *Full ecosystem* fix) | | | |
| G1 scripted player, `examples/volcanic.json` | abyss, divided, full ecosystem; survivors with an aimed shower; giant not reached in this run | | | |
| Viewer (headless screenshot, `--set sensing=1`, inspector) | renders; sensor weights fit the panel | | | |

Lint: `ruff check .` — clean.
Speed: ≈ 545 steps/s with sensing off, ≈ 380 with sensing on (563 before F3; seed 1, 3000 steps).
Game panel (headless screenshot, all milestones reached): the longer *Full ecosystem* text wraps and fits.

## Failures
None. During the work: `test_total_extinction_is_not_survival` failed once the random stream changed
(an immigrant pre-empted the reseed) — the test now disables immigration; the idle-player control
found a free *Full ecosystem* milestone — fixed with a regression test. The code review's three
regression tests (edge-row densities, kin predators, tracker/cell mismatch in saves) failed before their fixes.
