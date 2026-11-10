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
