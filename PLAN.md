# PLAN

F5e Prey defence (owner's choice 2026-11-11, after the world study). Goal: a world where cells live long enough for
within-life mechanisms (learning, regulation, differentiation). Branch `feat/f5e-prey-defence` off `36b4d21`; PR #21
(F3 P1) and `exp/world-study` touch the same docs and are merged before this one.

## Checklist
1. [x] Pilot (throwaway engine, 30k, seeds 41/43): strength 0.8 / upkeep 0.2 passes 3/4 runs (below)
2. [x] Design and pre-registered rules (this file); ADR-0011
3. [ ] Engine: `Config.defence*`, `Cell.armor_p`, failed attacks in predation, stats; no RNG when off
4. [ ] Save v8 (`armor_p` per cell, `defended` counter); Rust loader v8, golden sets regenerated
5. [ ] Tests; off-world fingerprints equal to `36b4d21` (8 configurations); speed off/on
6. [ ] Experiment `scripts/f5e_experiment.py`, 30k steps, 20 pairs; verdict per the rules below
7. [ ] Review (code-review-security), docs (ROADMAP, ARCHITECTURE, CLAUDE.md, USER_MANUAL, CHANGELOG, TEST.md)

## Pilot (2026-11-11, before this design; pass rule fixed before running)
Throwaway engine (scratchpad worktree), immigration 0, flat day/night + seasons and `volcanic.json`, seeds 41/43,
30k steps. Pass = on all 4 runs median life >= 20 (second half), population >= 300, no extinction, predators present in
the last third. No setting passed. Strength 0.8 / upkeep 0.2: median life 36, 33, 21, 26 (default 5-8), kills 55-81%
of deaths (default 95-97%), mean armour 0.94-0.98, predators 0% / 4.9% / 21% / 15% in the last third: 3/4. The owner
chose to build with these values, accepting the 3/4 after seeing the data (recorded as a post-hoc choice).

## Design
- **Evolvable propensity `armor_p`** in [0, 1], outside the genome like `sex_p`, `plast_p`, `hgt_p`: seeded cells and
  immigrants draw it after the `hgt_p` draw; children inherit the dividing parent's, mutated with its `mut_sigma`.
- **Effect**: when a predator picks a prey, the attack fails with probability `armor_p x defence_strength` (default 0.8,
  capped at 0.95 so no cell is immune): the predator gets nothing, the prey is untouched. One `rand()` per attack on
  a prey, only in the active arm. Counter `defended` (cumulative failed attacks, saved).
- **Cost**: `defence_upkeep x armor_p` per step (default 0.2), paid in the neutral arm too.
- **Neutral arm** `defence_neutral`: `armor_p` inherited and mutated, cost paid, no effect, no draw.
- Predators have no counter-trait (one mechanism at a time); armour is expected to approach its maximum.

## Experiment (P1 standard, rules fixed before any run)
Immigration 0; flat day/night + seasons and `examples/volcanic.json`; seeds 1, 3, ..., 19 = 20 pairs; 30k steps;
second half; descendants only. Arms: off / on / neutral (cost 0) / neutral_cost (cost 0.2) / control (neutral, cost 1.0).
1. **Primary, the world**: the `on` arm is the "long-life world" if, in >= 16/20 pairs: median age at death of
   descendants >= 20, mean population >= 300, no extinction, predators present (mean share > 0) in the last third.
2. **Positive control**: mean `armor_p` control < neutral in >= 16/20, else rules 3-4 are not claimed.
3. **Is defence favoured?** `armor_p` on vs neutral_cost: higher in >= 16/20 -> beneficial; lower -> harmful.
4. Net selection: on vs neutral, same thresholds.
5. **Consequences against neutral_cost** (same cost, no effect): median life, kills / deaths, population, predator
   share; a direction is claimed only at >= 16/20. On vs off is reported too.
6. A count of exactly 16/20 is reported as "at the threshold, not confirmed on new seeds".
