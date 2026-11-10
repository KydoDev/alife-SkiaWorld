# Test Report

Last run: 2026-11-10 — F5a Two parents (working tree before the F5a commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 159 tests; new `tests/test_sex.py`) | 159 | 0 | 0 | 98.8% (`worldsim/`, excl. render) |
| Off-world identity: full-state fingerprints vs the F3 and F4 commits (sex off; F4 rules on) | identical | | | |
| F5a experiment (`scripts/f5_experiment.py`, 40 runs x 10k steps), after the review fix | sex_p not selected (6/10, cost 5/10); no consistent consequence | | | |
| F5a confirmation of lower diversity (seeds 11–19, arms off/on) | 6/10: not confirmed | | | |
| F5a positive control (`sex_cost=4`, pre-registered: lower than neutral in >= 8/10) | 6/10: did not fire, assay blind | | | |
| End-to-end `run.py --set sex=1 --set sex_cost=0.5 --save-every 300`, then `--resume` | same final stats as the straight run | | | |

Lint: `ruff check .` — clean.

## Failures
None at the end. During the work: the review's regression tests failed before their fixes (partner propensity
inherited by the child; unaffordable `sex_cost` driving energy negative). The first experiment run was
invalid (transmission artefact) and was discarded; the confirmatory run started on it was stopped.
