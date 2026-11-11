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


---

<!-- archived 2026-11-10 -->

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


---

<!-- archived 2026-11-10 -->

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


---

<!-- archived 2026-11-10 -->

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


---

<!-- archived 2026-11-10 -->

# Test Report

Last run: 2026-11-10 — P1 experiment power (working tree before the P1 commit)

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
| P1 positive control (`sex_cost=4` vs neutral, 30k steps, 20 pairs; pre-registered >= 16/20) | A 16/20, B 16/20: fires | | | |
| P1 re-ask (sex cost 0 vs neutral, same pairs, both settings must agree) | higher 8/20 (A), 9/20 (B): no detectable selection | | | |
| End-to-end `run.py --set sex=1 --set sex_cost=0.5 --save-every 300`, then `--resume` | same final stats as the straight run | | | |

Lint: `ruff check .` — clean.

## Failures
None at the end. During the work: the review's regression tests failed before their fixes (partner propensity
inherited by the child; unaffordable `sex_cost` driving energy negative). The first experiment run was
invalid (transmission artefact) and was discarded; the confirmatory run started on it was stopped.


---
## Archived 2026-11-10 (before F5c)

# Test Report

Last run: 2026-11-10 — F5b Diet plasticity (working tree before the F5b commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 172 tests; new `tests/test_plasticity.py`) | 172 | 0 | 0 | 98.8% (`worldsim/`, excl. render) |
| Off-world identity: full-state fingerprints vs `c3e1c43` (default, day/night + sensing, F4, F5a, vents + rock) | identical | | | |
| Speed (default world, 2000 steps): off / on | 583 / 406 steps/s (before: 577) | | | |
| F5b positive control (`plastic_upkeep=0.2`, neutral; pre-registered >= 16/20) | 20/20: fires | | | |
| F5b cost-matched question (`plast_p` on vs neutral_cost, 20 pairs, 30k steps) | higher 19/20: beneficial | | | |
| F5b net selection (on vs neutral) / power at the real cost (neutral_cost < neutral) | 14/20, 15/20: not detected | | | |

Lint: `ruff check .` — clean.

## Failures
None at the end. The review's two regression tests (no-feeding-gene cell fed as a generalist; loader accepting a
moved diet in a frozen arm) failed before their fixes; the first experiment run was superseded. One new test compared a float distance to exactly 0 and failed on
rounding (~1e-16); the assertion now uses a tolerance.


---
## Archived 2026-11-10 (before the G2 M2 open-points run)

# Test Report

Last run: 2026-11-10 — F5c Horizontal gene transfer (working tree before the F5c commit)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 195 tests; new `tests/test_hgt.py`) | 195 | 0 | 0 | 98.9% (`worldsim/`, excl. render) |
| Rust `cargo test` + `tests/test_g2_golden.py` after the v7 golden regeneration | green / 10 passed | 0 | | `hashes.csv` unchanged |
| Off-world identity: full-state fingerprints vs `367aecd` (default, day/night + sensing, F4, F5a, vents + rock, F5b on) | identical | | | |
| Speed (default world, idle machine): off / on | 539–560 / ~526 steps/s (before: 543–560) | | | |
| F5c positive control (`hgt_upkeep=0.2`, neutral; pre-registered >= 16/20) | 20/20: fires | | | |
| F5c cost-matched (`hgt_p` on vs neutral_cost) | 10/20; confirmation 13/20 lower: no detectable effect | | | |
| F5c net selection (on vs neutral) | lower 16/20; confirmation 18/20: selected against | | | |

Lint: `ruff check .` — clean.

## Failures
None at the end. During the work: the six G2 golden tests failed as expected after the save bump to v7 and
passed after regenerating the golden sets. The review found no defect; its notes added one loader check and
one test.


---
## Archived 2026-11-11 (before the F3 P1 re-run, merged after G2 M2 open points)

# Test Report

Last run: 2026-11-10 — G2 M2 open points (vent field, seabed, gradient off numpy; CI `--locked` + audit), working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 198 tests; new `test_terrain_transcendentals_come_from_libm`) | 198 | 0 | 0 | 98.85% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (14 tests) | 0 | | |
| `cargo deny --locked check advisories` (cargo-deny 0.20.2, default config) | advisories ok | | | |
| Golden sets regenerated (default + volcanic, 1000 steps) vs committed | identical (`hashes.csv`, `rng.json`, decompressed `start.json.gz`) | | | |
| Old vs new expressions (plumes with x-wrap, `seabed_heights` x150 seeds, `planet.png` gradient) | bit-identical | | | |

## Notes
- The new regression test cannot fail on this CPU (no AVX-512: numpy already used libm); it guards
  the Linux CI runner.


---
## Archived 2026-11-11 (before the world study)

# Test Report

Last run: 2026-11-10 — F3 re-run at the P1 standard (branch `exp/f3-p1` merged with main `36b4d21`)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 198 tests) | 198 | 0 | 0 | 98.9% (`worldsim/`, excl. render) |
| Reproducibility on main after #19 (libm light): `flat_seasons` seed 1 `free`, 30k steps, re-run | identical CSV row | | | |
| F3 P1 positive control (`sense_upkeep=0.5`; pre-registered >= 16/20) | 16/20, then 19/20 on seeds 21–39: fires | | | |
| F3 P1 phototaxis (`w_light` free vs off) | 13/20, then 16/20: lean, not established | | | |

Lint: `ruff check .` — clean.

## Failures
None. No engine code changed in this piece (experiment script and docs only).


---
## Archived 2026-11-11 (before the F5e run)

# Test Report

Last run: 2026-11-11 — World study (branch `exp/world-study`, stacked on `exp/f3-p1`)

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 198 tests) | 198 | 0 | 0 | 98.85% (`worldsim/`, excl. render) |
| World study coarse sweep (9 settings x 4 runs, 10k) | no setting meets the criteria | | | |
| Extended sweep with `spec_exp` (12 settings x 4 runs, 10k) | no setting meets the criteria | | | |
| Check of the closest setting (20 P1 pairs, 30k; predator criterion relaxed post hoc) | 7/20 pass: rejected | | | |

Lint: `ruff check .` — clean.

## Failures
None. No engine code changed in this piece (study script and docs only).


---
## Archived 2026-11-11 (before G2 M4 part A)

# Test Report

Last run: 2026-11-11 — F5e prey defence (branch `feat/f5e-prey-defence`), working tree before the docs commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 211 tests; new `tests/test_defence.py`, 13 tests) | 211 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (14 tests) | 0 | | |
| Golden sets regenerated for save v8 (default + volcanic) | `hashes.csv` unchanged | | | |
| Off-world fingerprints, 8 configurations, vs `36b4d21` | identical | | | |
| Speed, default world (best of 3, 1500 steps) | main 574, defence off 555, on 530 steps/s | | | |

## Notes
- Off vs main speed differs by about 3%, within run-to-run noise on this machine; the predation branch gains
  one boolean test.
- Experiment results are in `docs/ROADMAP.md` (F5e), not here.

---
<!-- archived 2026-11-11, before the G2 M4 part B run -->

# Test Report

Last run: 2026-11-11 — G2 M4 part A (C ABI and render in Rust), branch `feat/g2-m4-unity`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 211 tests) | 211 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (23 tests; new `tests/ffi.rs` 6, `tests/golden_render.rs` 2, `ffi` unit 1) | 0 | | |
| Golden renders (`render_start`, `render_end`) vs Rust, both sets | equal byte for byte | | | |
| `hashes.csv` after computing light at load | unchanged | | | |
| Built `worldsim_core.dll` called from Python `ctypes` (volcanic, 1000 steps) | hash equal to `hashes.csv` | | | |

## Notes
- No Python engine change: `scripts/g2_golden.py` only gains the two renders (`--renders-only`).
- Security review of the C ABI: no blocking issue; follow-ups applied (bounded error messages, shared references for read-only calls, no panic in error handling, `panic = "abort"` refused at compile time).

---
<!-- archived 2026-11-11, before the G2 M5 item 2 run -->

# Test Report

Last run: 2026-11-11 — G2 M4 part B (Unity front-end), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 211 tests) | 211 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Unity EditMode (`unity/`, batchmode, Unity 6000.5.6f1) | 7 | 0 | 0 | |
| Rust (`engine-rs`) | not re-run: unchanged since the last green run (M4 part A) | | | |

## Notes
- Unity tests: ABI version; golden hashes through P/Invoke in uneven chunks (default, volcanic); start render
  equal to Python's byte for byte (default, volcanic); bad save and short buffer raise with the kernel message;
  disposed world throws. Not in CI (Unity needs a licence): run locally (DEVELOPER_GUIDE, Unity front-end).
- Windows player build checked on screen via screenshots (surface on top, play/pause/step/speed). One unexplained
  pause after a click on `+` then `Space`, not reproduced in two tries; recorded in G2_PLAN, not a test failure.

---
<!-- archived 2026-11-11, before the G2 M5 item 3 run -->

# Test Report

Last run: 2026-11-11 — G2 M5 item 2 (`defence` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 228 tests) | 228 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (golden sets `default`, `volcanic`, `defence`, `defence_neutral`; loader bounds on a defence save) | 0 | | |
| `defence` and `defence_neutral` sets, kernel vs Python | equal at all 1000 steps | | | |
| `default`, `volcanic` `hashes.csv` regenerated | byte-identical | | | |
| M3 benchmark (default flags), before / after | 6.38 / 6.11, 8.08 / 7.92, 5.43 / 5.54 M cell-updates/s | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.
- The review also ran a reseed-after-extinction world with armour against the kernel (scratch, not committed): equal.

---
<!-- archived 2026-11-11, before the G2 M5 item 4 run -->

# Test Report

Last run: 2026-11-11 — G2 M5 item 3 (`hgt` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 241 tests) | 241 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (golden sets `default`, `volcanic`, `defence`, `defence_neutral`, `hgt`, `hgt_neutral`; loader bounds for `armor_p` and `hgt_p`) | 0 | | |
| `hgt`, `hgt_neutral` sets, kernel vs Python | equal at all 1000 steps | | | |
| Earlier four sets' `hashes.csv`, regenerated | byte-identical | | | |
| M3 benchmark, this build vs previous commit side by side | equal within noise (50k slower for both: machine state) | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.

---
<!-- archived 2026-11-11, before the G2 M5 item 5 run -->

# Test Report

Last run: 2026-11-11 — G2 M5 item 4 (`plasticity` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 254 tests) | 254 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (8 golden sets; loader bounds for `plast_p`, diet, `hgt_p`, `armor_p`) | 0 | | |
| `plasticity`, `plastic_neutral` sets, kernel vs Python | equal at all 1000 steps and in both renders | | | |
| Earlier six sets' `hashes.csv`, regenerated | byte-identical | | | |
| M3 benchmark vs previous commit, 3 alternating runs | 800 +9%, 10k -4%, 50k -3% | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged (the render change is covered by the golden renders).

---
<!-- archived 2026-11-11, before the G2 M5 item 6 run -->

# Test Report

Last run: 2026-11-11 — G2 M5 item 5 (`sex` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 267 tests) | 267 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (10 golden sets; `genome_distance` vs Python on 700 pairs, 80 with a subnormal maximum; loader bounds for every ported propensity) | 0 | | |
| `sex`, `sex_neutral` sets, kernel vs Python | equal at all 1000 steps | | | |
| Earlier eight sets' `hashes.csv`, regenerated | byte-identical | | | |
| CPython `vector_norm` re-implementation vs `math.dist` (scratch, 2M pairs) | 0 mismatches | | | |
| M3 benchmark vs previous commit, 2 alternating rounds | 800 +2%, 10k -5%, 50k +2% | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.

---
<!-- archived 2026-11-11, before the G2 M5 item 7 run -->

# Test Report

Last run: 2026-11-11 — G2 M5 item 6 (`sensing` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 281 tests) | 281 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (12 golden sets; `genome_distance` vs Python on 700 pairs; loader bounds for every ported propensity) | 0 | | |
| `sensing`, `sensing_volcanic` sets, kernel vs Python | equal at all 1000 steps | | | |
| Earlier ten sets' `hashes.csv`, regenerated | byte-identical | | | |
| M3 benchmark vs previous commit, 2 alternating rounds | 800 cells +1%, 10k +4%, 50k -1% (noise level) | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.

---
<!-- archived 2026-11-11, before the G2 M5 item 8 run -->

# Test Report

Last run: 2026-11-11 — G2 M5 item 7 (`open_genome` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 294 tests) | 294 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (14 golden sets; `genome_distance` vs Python on 700 pairs; loader bounds for every ported propensity and the rule genes) | 0 | | |
| `open_genome`, `rules_neutral` sets, kernel vs Python | equal at all 1000 steps | | | |
| Earlier twelve sets' `hashes.csv`, regenerated | byte-identical | | | |
| M3 benchmark vs previous commit, alternating rounds | means of six rounds, 800 cells 0%, 10k +2%, 50k -2% (the first three rounds showed 50k -9%, the next three, run in the other order, +4%: noise level); Cell grows from 384 to 408 bytes (the rule Vec) | | | |

## Notes
- Unity EditMode tests not re-run: the C ABI and `unity/` are unchanged.

---
<!-- archived 2026-11-11, before the ADR-0012 piece 1 run -->

# Test Report

Last run: 2026-11-11 — G2 M5 item 8 (combined golden sets), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 322 tests) | 322 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (18 golden sets; `genome_distance` vs Python on 700 pairs; loader bounds and the rule budget) | 0 | | |
| `combined`, `combined_reseed`, `combined_width2`, `open_genome_unsensed`, kernel vs Python | equal at all 1000 steps | | | |
| Earlier fourteen sets' `hashes.csv`, regenerated | byte-identical | | | |

## Notes
- No kernel code changed: benchmark not re-run. Unity EditMode tests not re-run (C ABI and `unity/` unchanged).

---
<!-- archived 2026-11-11, before the ADR-0012 piece 2 run -->

# Test Report

Last run: 2026-11-11 — ADR-0012 piece 1 (seeding in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 323 tests) | 323 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked` | green (18 golden sets; seeding vs CPython on 13 seeds; `genome_distance` on 700 pairs) | 0 | | |

## Notes
- No step, loader or ABI change: benchmark and Unity tests not re-run.

---
<!-- archived 2026-11-11, before the ADR-0012 piece 3 run -->

# Test Report

Last run: 2026-11-11 - ADR-0012 piece 2 (numpy pairwise mean in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 324 tests) | 324 | 0 | 0 | 98.87% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (18 golden sets; numpy mean on 34 lengths; seeding on 13 seeds) | 0 | | |

## Notes
- First candidate (accumulator seeded with the first element) failed at n = 4; the identity-seeded sum is the one
  committed. No step, loader or ABI change: benchmark and Unity tests not re-run.

---
<!-- archived 2026-11-11, before the ADR-0012 piece 4 run -->

# Test Report

Last run: 2026-11-11 - ADR-0012 piece 3 (procedural terrain in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 326 tests) | 326 | 0 | 0 | 98.94% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (18 golden sets; 44 terrains and 27 plumes; numpy mean on 34 lengths; seeding on 13 seeds) | 0 | | |

## Notes
- Terrain and plume digests equal at the first run. The pytest check recomputes every case except the two
  10 000-wide ones (time); the Rust test covers all of them. No step, loader or ABI change: benchmark and Unity
  tests not re-run.

---
<!-- archived 2026-11-11, before the ADR-0012 piece 5 run -->

# Test Report

Last run: 2026-11-11 - ADR-0012 piece 4 (`World::new` in the Rust kernel), `main`, working tree before the commit

> Archive protocol: before overwriting this file, append its current content to
> `test_history.md` under a dated separator.

## Summary
| Suite | Passed | Failed | Skipped/xfail | Coverage |
|-------|--------|--------|---------------|----------|
| Unit + integration (`tests/`, 340 tests) | 340 | 0 | 0 | 98.94% |
| `ruff check .` | clean | | | |
| Rust (`engine-rs`): `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`, `cargo test --locked --release` | green (20 golden sets; 52 creations; 44 terrains and 27 plumes; numpy mean; seeding) | 0 | | |

## Notes
- Full `g2_golden.py --all` regeneration (2 min 18 s): the 18 existing `hashes.csv` and `terrain.json` unchanged.
- No step, loader or ABI change: benchmark and Unity tests not re-run.
