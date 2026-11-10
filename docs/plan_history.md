# Plan history

Closed plans, moved verbatim from `PLAN.md`.

---

## Closed 2026-11-10

### PLAN — F1 Foundations

Branch: `main` (owner decision 2026-11-10: work on main for now, single commit for the whole of F1). Exit criterion (ROADMAP F1): re-run a simulation, see its species tree and a novelty-over-time chart.

## Checklist
1. [x] Baseline: steps/s and `stats.csv` for `run.py --seed 1 --steps 3000` (after the bonds-order change)
2. [x] Energy-conservation test on a closed system (no sources/sinks)
3. [x] Canonical bond order: `Cell.bonds` as insertion-ordered dict, so it survives save/load
4. [x] Save/load (ADR-0002): safe versioned format; resume == uninterrupted run, per cell
5. [x] Species tracking (ADR-0003): pure observer, bounded memory, saved with the world, tree plot
6. [x] Novelty metric: simplified evolutionary activity, immigrant roots excluded, chart
7. [x] Profiling: cProfile table + steps/s in docs; optimize only if trivial
8. [x] Exit demo: seed 1 ~10k steps, resume mid-run == straight run, read tree + novelty PNGs

## Notes
- Each piece has its own tests; F1 lands as one commit (owner decision).
- Tracker must not call `World.rng` nor influence dynamics: same seed → same per-cell history with tracking on/off.
- Novelty without a neutral shadow model has an arbitrary threshold: name it honestly and document the limitation.

## Baseline (item 1)
`python run.py --steps 3000 --seed 1 --out runs/baseline` after the bonds-dict change:
3000 steps in ~5 s (~600 steps/s), final pop 831 (photo 669, sapro 55, pred 107), colony 633, lineages 49.
`runs/baseline/stats.csv` is the reference for observer-purity checks (git-ignored, regenerate with the same command).

---

## Closed 2026-11-10

# PLAN — F2 Living environment + world seed

## Checklist
1. [x] Re-verify F1 exit criterion and record F2 baseline (seed 1, 10k steps, 489 steps/s)
2. [x] F2a variable light: day/night + seasons (pure function of step, default off) + tests
3. [x] F2a experiment: does mean_mut rise in a variable environment? (seeds 1, 7)
4. [x] F2b terrain: rocks honoured in every placement path + tests
5. [x] F2b vents + chemosynthesis (10th gene `chemo`, 4th strategy) + cross-impact
6. [x] F2b experiment: do chemo specialists colonise dark vents?
7. [x] F2c worldgen module: planet from image or JSON form, hashlib seed, own RNG
8. [x] Save format v2 (terrain maps in the save) + ADR-0004
9. [x] Security review of image/JSON loading; perf check vs baseline
10. [x] Docs, CHANGELOG, TEST.md, ROADMAP results; single F2 commit (ask before push)

## Detail
- Baseline: `runs/f2base` (seed 1, 10k steps): pop 903, species 82, novelty 375, extinctions 0.
- Adding the `chemo` gene changes every seed's history (one more random draw per genome):
  F1 numbers stay valid for the F1 commit; re-record baseline after item 5.
- Terrain generation uses its own RNG seeded from the world seed, never `World.rng`.
- Rocks: cells never occupy them; they block light like an opaque cell; organic matter
  ignores them (documented simplification) so energy bookkeeping is unchanged.

---

## Closed 2026-11-10

### PLAN — G1 "Planet in a jar" prototype

## Checklist
1. [x] Interventions (`worldsim/play.py`): nutrients, meteorite, mountain/dig, volcano — instant, RNG-free edits of saved state
2. [x] Divine-energy budget (regenerates per step) and 5 milestones evaluated from stats; `GameRules` dataclass
3. [x] `game.py` pygame front-end: tools 1-4, click to act, budget bar, milestone list, toasts, legend
4. [x] Tests: grid/bond consistency and energy accounting after each intervention, determinism with replayed actions, milestones
5. [x] Headless playtest: scripted player reaches milestones; tune costs so the budget matters
6. [x] docs/USER_MANUAL.md, ROADMAP G1, README, CHANGELOG, TEST.md; single G1 commit
7. [x] Exit check by the owner: is it fun? (owner playtest 2026-11-10: positive, no change requests)

## Detail
- Roadmap G1: "Photo or form -> planet, 3-4 interventions, 5 milestones. Check whether it is fun before investing in the port."
- Engine stays headless and deterministic. Interventions use no RNG and only touch state that is already saved
  (cells, organic, terrain maps), so save/resume stays bit-exact; same seed + same actions at the same steps = same history.
- Game rules (costs, regen, milestone thresholds) live in `GameRules`, not `Config`: they never change the simulation.
- Out of scope (G3): saving game progress (budget, milestones), naming species, tree-of-life view, sharing.
- Milestones (first draft): predators (>= 50), deep life (>= 50 chemosynthesizers), colonies (>= 50% bonded, pop >= 300),
  evolution (25 new species established), survivor (population falls below 30% of its peak, then recovers to 80%).

---

## Closed 2026-11-10

### PLAN — F3 Sensors and behavior

## Checklist
1. [x] Baseline before any edit: 563 steps/s (seed 1, 3000 steps); pre-F3 10k-step runs for speciation/novelty
2. [x] 6 sensor genes appended (weights in [-1,1]); `Config.sensing` (off by default), `sense_noise`, `sense_upkeep`
3. [x] Directed movement: score the 8 tiles + staying put; move to the best; random walk when sensing is off
4. [x] Species distance normalised per gene (ref. 10 genes); save VERSION 3; ADR-0005
5. [x] Tests: determinism, sensing off == random walk, phototaxis/flee unit cases, save v3 round-trip, bounds
6. [x] Experiment: sensing on/off x seeds 1, 7 x immigration on/off; hunting, fleeing, vertical migration
7. [x] Cross-impact: viewer/game inspector, G1 idle + bot recalibration; docs, CHANGELOG, TEST.md; one commit

## Detail
- Roadmap F3: perceive the 8 neighbouring tiles (light, organic, cells, kinship); directed movement with genome weights.
  Experiment: do hunting, fleeing, day/night vertical migrations emerge?
- Inputs per candidate tile (radius 1, seen from the mover's tile): light, organic matter, chemical energy,
  kin (same lineage) and strangers among the mover's neighbours adjacent to that tile, danger (predator share of
  those strangers). Score = sum(weight * input) + noise; the current tile is a candidate (staying costs nothing).
- Kinship uses `lineage`, never `species` (the tracker is a pure observer).
- Honest limit: predation already strikes any adjacent cell and perception is radius 1, so hunting can barely
  emerge; fleeing, phototaxis and vertical migration can. No widening of the radius to rescue the hypothesis.
- Control: same engine with `sensing=False` (sensor genes drift neutrally). Selection signature: `mean_w_*`
  leaving 0.5 with sensing on and staying near 0.5 with it off. Immigration-off arm against the F2a confound.
- Sensing is computed only after the movement gate passes; signed weights precomputed in `express()`.
