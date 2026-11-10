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
