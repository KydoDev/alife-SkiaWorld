# Test Report

Last run: 2026-11-10 — F4 Open genome (working tree before the F4 commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 138 tests; new `tests/test_open_genome.py`) | 138 | 0 | 0 | 98.6% (`worldsim/`, excl. render) |
| Off-world identity: fingerprint vs the F3 commit (local, Windows) and two F3 experiment arms re-run; CI test asserts no rule code runs | identical | | | |
| F4 experiment (`scripts/f4_experiment.py`, 30 runs x 10k steps) | pre-registered verdict null overall (5/10); volcanic 4/5 | | | |
| F4 confirmatory (volcanic, seeds 11–19, pre-registered >= 4/5) | 5/5: rules earn their keep on the volcanic planet | | | |
| Viewer inspector (rule lines measured against the panel width) | widest line 240 px of 244 | | | |

Lint: `ruff check .` — clean.
Speed: no measurable cost with the open genome off (same as F3 within noise); small with rules on, not precisely measured.
End-to-end: `run.py` with `--set sensing=1 --set open_genome=1 --save-every 300`, then `--resume` from step 300: same final stats as the straight run.

## Failures
None. The F4 security review's loader cases (short rows, huge JSON numbers, booleans in rules, a broken RNG
state) failed before the fix: they crashed with ValueError/OverflowError instead of `SaveFormatError`.
