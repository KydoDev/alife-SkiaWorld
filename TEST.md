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
