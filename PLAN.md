# PLAN

World study: find settings where cells live long enough for within-life mechanisms (learning, regulation,
differentiation) to have something to act on. A parameter study, not a new mechanism: the default world is not
changed; the result is a named set of overrides for later experiments.

## Checklist
1. [x] Death probe: 96-97% of deaths are predation (below)
2. [x] Goal and selection criteria (this file), written before the sweep
3. [x] Coarse sweep of predation pressure, 10k steps, seeds 41 and 43, both planets
7. [ ] Extended sweep with spec_exp (rules below), same criteria
4. [ ] Pick a setting by the criteria; check it at 30k steps on 20 pairs
5. [ ] Re-run the regulator pilot in the chosen world
6. [ ] Docs (ROADMAP, CHANGELOG, TEST.md), commit, ask to push

## Why (probes, 2026-11-10/11)
F5d, the F3 P1 re-run and the regulator pilot all hit the same limit: median life 6-8 steps, 0.4-2.5 sensed moves
per life, chains of rules in 0-7% of cells. Death probe (immigration 0, seeds 41/43, steps 5-10k): 96-97% of
deaths are kills by predators, which are 4-8% of cells; deaths of old age are a few dozen of 200-375 thousand.

## Sweep (scratchpad first, then `scripts/world_study.py`)
Immigration 0; flat day/night + seasons and `examples/volcanic.json`; seeds 41 and 43 (not the P1 seeds 1-39);
10k steps, measured over steps 5-10k. Grid: `pred_eff` in {0.5, 0.35, 0.25} x `pred_upkeep` in {0.3, 0.6, 1.0}
(defaults 0.5, 0.3). Measures: median age at death of descendants, mean population, predator share, killed share
of deaths, share of cells in colonies of >= 4, extinctions.

## Selection criteria (fixed before the sweep)
A setting qualifies if, on all 4 planet x seed runs:
- median age at death of descendants >= 3 x the default world's (>= ~20 steps);
- mean population >= 300 and no extinction;
- predators keep >= 2% of cells (the trophic level survives).
Among qualifying settings, pick the one closest to the defaults (fewest and smallest changes). If none
qualifies, report it and ask the owner before widening the grid.

## Check (30k steps, P1 pairs)
The chosen setting on the 20 P1 pairs, 30k steps: report median life, population, predator share, extinctions.
It is accepted as the "long-life world" if the criteria hold in >= 16/20 pairs.

## Coarse sweep result (2026-11-11, `docs/world_study.csv`)
No setting qualifies. Best: `pred_eff` 0.25, `pred_upkeep` 1.0 (median life 21-29 in 3 runs, 6 on volcanic 41;
predators < 2% in 3 runs). Killer probe (default world): 62-77% of kills are made by cells whose dominant strategy is
photo or chemo with a small predatory share; 38-68% of cells have `pred_k` > 0.01. Predation is diffuse, so costs
on specialist predators barely touch it. The owner approved widening the grid.

## Extended sweep (fixed before running; same criteria, same seeds and steps)
`spec_exp` in {3, 4} (default 2: a higher exponent shrinks the small shares of mixed diets, so `pred_k` of mostly
photo cells falls) x `pred_eff` in {0.5, 0.35, 0.25} x `pred_upkeep` in {0.3, 1.0}: 12 settings x 4 runs.
"Closest to the defaults" ranks first by the number of changed parameters, then by the size of the change.

## Extended sweep result (2026-11-11, `docs/world_study_spec.csv`)
No setting qualifies. Long lives occur only where predators fall below 2% of cells: the life and predator criteria
conflict. Closest: `spec_exp` 3, `pred_eff` 0.25, `pred_upkeep` 1.0 -> median life 35, 37, 41, 52 (5-7x the
default), population 1268-1398, no extinction, predators 0.5-1.8% (fails only the >= 2% criterion). Other
long-life settings are unstable across runs (e.g. 4/0.35/1.0: median life 9-130, predators 0-3.1%).
Next step needs the owner: relaxing the predator criterion would be a change made after seeing the data.
