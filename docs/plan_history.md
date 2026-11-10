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
