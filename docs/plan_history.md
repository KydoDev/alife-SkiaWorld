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


## F4 Open genome (closed 2026-11-10)

### Checklist
1. [x] F4 design: rule genome, mutation operators, neutral arm, metrics and verdict rule fixed before running
2. [x] Engine: `Cell.rules`, rule expression, mutation (point/dup/del/de novo), upkeep, cap; off-world bit-identical
3. [x] Persistence v4 (rules in cells, validated); stats columns; viewer inspector
4. [x] Tests: off-world identity, operators, effects, neutral arm, resume, hostile saves
5. [x] Experiment `scripts/f4_experiment.py` (3 arms x 2 planets x 5 seeds, 10k steps) and verdict
6. [x] ADR-0006, ROADMAP, ARCHITECTURE, CHANGELOG, TEST.md, USER_MANUAL; security review of save parsing
7. [ ] Local commit; ask the owner before pushing

### Design (item 1)
Roadmap level 2: "if I perceive X then I do Y with intensity Z", with the number of genes decided by evolution.

- **Representation**: the 16 fixed genes stay as they are. A cell also carries `rules`, a variable-length list
  of rule genes, each 4 values in [0, 1]: `(condition, threshold, target, intensity)`.
  - condition (5): always · own energy above / below threshold · light at own tile above / below threshold
    (energy normalised by `div_max`, light by `light_max`; light covers both depth and day/night).
  - target (7): one of the 6 F3 sensor weights (movement), or the division threshold.
  - intensity: `2v − 1`. While the condition holds, the rule adds it to that sensor weight, or shifts the
    division threshold by `intensity × rule_div_shift × (div_max − div_min)`.
  - Conditions depend only on the mover's own state, so active rules collapse into effective weights once per
    cell per step (cheap); cells with no rules take the F3 path unchanged.
- **Mutation at division** (only when `open_genome` is on, so the off-world draws no extra random numbers):
  point mutation of every rule value with the cell's `mut_sigma`; then with `rule_dup_rate` duplicate a random
  rule (inserted next to it), `rule_del_rate` delete one, `rule_new_rate` add a random new rule (the de novo
  source: seeded cells and immigrants start with no rules). Hard cap `max_rules`.
- **Cost**: `rule_upkeep` per rule per step, so genomes do not bloat for free.
- **Neutral arm** `rules_neutral`: rules exist, mutate, duplicate, delete and cost the same, but have no effect.
- **Species** stay defined on the 16 fixed genes (tracker untouched): genome growth cannot inflate novelty.
  Rule innovation is measured separately.
- **Save v4**: each cell row gains its rules; loader checks count ≤ `max_rules`, 4 values each, all in [0, 1].

Assumptions to confirm: fixed vocabulary of conditions and targets (open in number and combination, not in
kind); movement rules act only with `sensing` on (the experiment runs with sensing on in every arm).
Entry criterion: the roadmap's "stalls even in a variable environment" was not shown (F2 novelty rose; F3
modest). The owner chose F4 on 2026-11-10; recorded in the ADR.

### Experiment and verdict rule (fixed before running)
`python scripts/f4_experiment.py --steps 10000`: arms F3 (open_genome off) / on / neutral, all with
`sensing=1`, immigration 0.5; planets: flat with day/night (`day_amplitude=1`) and `examples/volcanic.json`;
seeds 1, 3, 5, 7, 9. Measured over steps 5–10k on descendants only.

Metrics: mean rule count; share of rules with a condition other than *always*; per rule type
(condition × target) frequency; fixed-gene novelty and species; population; steps/s.

Verdict:
- **Rules earn their keep** if the mean rule count with rules on exceeds neutral in ≥ 8 of 10 planet × seed
  pairs.
- **A behaviour is selected** if the same rule type (condition × target, with the sign of its mean intensity)
  is among the 3 most enriched on vs neutral in ≥ 6 of 10 pairs.
- Otherwise the result is null, reported as such.

### Result of the main run, and a confirmatory test (fixed before running it)
Main run (2026-11-10): **null** by the rule above — rules on > neutral in 5/10 pairs; no rule type in the top 3
in >= 6 pairs. Post-hoc hint: on `volcanic.json` rules on > neutral in 4/5 seeds (mean 1.75 vs 0.82 rules),
on the flat day/night world 1/5. Confirmatory test: `volcanic.json`, arms on / neutral, new seeds 11 13 15 17
19. The hint is confirmed if rules on > neutral in >= 4 of 5 new seeds; otherwise it was noise.


## F5a Two parents (closed 2026-11-10)

### Checklist
1. [x] F5a design: two parents (sexual reproduction) only; plasticity, learning, transfer are later steps
2. [x] Engine: evolvable `Cell.sex_p`, partner search (radius 2), uniform crossover, `sex_cost`; off-world identical
3. [x] Persistence v5 (sex_p in cells, validated); stats; viewer inspector
4. [x] Tests: off-world never runs sex code, crossover, partner rules, neutral arm, resume, hostile saves
5. [x] Experiment `scripts/f5_experiment.py` (4 arms x 2 planets x 5 seeds, 10k steps), verdict, confirmation
6. [x] ADR-0007, ROADMAP, ARCHITECTURE, CHANGELOG, TEST.md, USER_MANUAL; security review of save parsing
7. [ ] Local commit; ask the owner before pushing

### Design (item 1)
ROADMAP F5 lists four mechanisms; one at a time, so F5a is **two parents** only.

- **Evolvable propensity**: with `Config.sex` on, each cell has `sex_p` in [0, 1], the probability of looking
  for a partner when it divides. Seeded cells and immigrants draw it at random; children inherit it with
  mutation (`mut_sigma`). Not a 17th gene: like the F4 rules it exists only when the feature is on, so the
  off-world draws no extra random numbers and stays bit-identical (no G1 recalibration).
- **Mating at division**: with probability `sex_p` the dividing cell looks at the cells within `mate_radius`
  (default 2: 24 tiles) for cells whose fixed-gene distance (`genome_distance`) is below `mate_distance`
  (own Config field, default 0.3; never the tracker's species or threshold) and picks one at random. The
  partner gives genes only, no energy.
- **Probe before coding** (2026-11-10, 5000 steps, no sex; flat day/night+seasons and volcanic, seeds 1, 7):
  85–96% of neighbour pairs are within 0.3, median distance 0.03–0.11 ≈ 1–2.5 mutation steps, only 1–6% of
  neighbours from another lineage. Mates are close relatives: recombination shuffles the recent mutations of
  nearby branches (the Fisher–Muller case), a real but weak test. Hence radius 2, to widen the pool; 0.3 still
  excludes cross-strategy hybrids. The experiment logs partner-found share and mean pair distance.
- **Recombination**: uniform crossover of the 16 fixed genes (each from either parent, p = 0.5), then the
  usual mutation; `sex_p` from the dividing parent only, then mutated (see the review note below). Rule genes (F4), if any, come from the
  dividing parent. Lineage and species bookkeeping follow the dividing parent.
- **Cost**: the dividing cell pays `sex_cost` (default 0) each time it mates, before splitting its energy (so
  no energy goes negative); no mate found = asexual division, no cost. A sexual-births counter is saved.
- **Neutral arm** `sex_neutral`: `sex_p` exists, is inherited and mutates, but mating never happens: the
  drift baseline for `sex_p`.
- **Save v5**: each cell row gains `sex_p` (finite, in [0, 1]; 0 when sex is off).

### Experiment and verdict rule (fixed before running)
`python scripts/f5_experiment.py --steps 10000`: arms off / on (cost 0) / on_cost (`sex_cost=1`, a fifth of
`body_cost`) / neutral; immigration 0.5; planets: flat with
day/night and seasons (`day_amplitude=1`, `season_amplitude=0.5`) and `examples/volcanic.json`; seeds
1, 3, 5, 7, 9. Measured over steps 5–10k on descendants only.

Metrics: mean `sex_p`; share of births that were sexual; population; species and novelty; genetic diversity
(mean per-gene standard deviation of the fixed genes).

Verdict:
- **Sex is selected** if mean `sex_p` with sex on (cost 0) exceeds neutral in >= 8 of 10 planet x seed pairs;
  **selected against** if it is lower in >= 8 of 10; otherwise no detectable selection. The same rule is
  applied to `on_cost` and reported separately (it separates "no benefit" from "cost outweighs benefit").
- Any positive verdict is claimed only after a confirmatory run on seeds 11–19 (>= 4 of 5), as in F4: the
  two-sided 8/10 rule fires by chance about 11% of the time.
- **Consequences of sex** (on vs off): reported as differences with their spread over seeds, no claim unless
  the sign agrees in >= 8 of 10 pairs. **No novelty claim**: recombinant children sit further from the
  dividing parent's species founder, so speciations can rise with no real invention.

### Result of the main run, and a confirmatory test (fixed before running it)
Main run (2026-11-10): sex_p with sex on (cost 0) lower than neutral in 8/10 pairs -> **selected against** by
the rule; on_cost lower in 7/10 (no detectable selection); genetic diversity lower with sex than without in
8/10. Partners were found in 94–98% of attempts, at a mean distance of 0.08–0.13.
Confirmatory test: all 4 arms, both planets, new seeds 11 13 15 17 19 (10 new pairs). Confirmed if the same
rule holds on the new pairs: on < neutral in >= 8/10 (selected against); diversity on < off in >= 8/10.
on_cost is reported with the same rule.

### The main run above is invalid (review, 2026-11-10); re-run
The F5a review found a transmission artefact: the child took the mate's `sex_p` half the time, and mates are
not chosen by their propensity, so the mean fell by about (share of matings / 2) x variance per generation with
no selection at all, in the on arms only. "Selected against" could come from that alone. Fix: `sex_p` is
inherited from the dividing parent only (test added). Also fixed: an unaffordable `sex_cost` drove energy
negative (now mating is skipped); consequence metrics are now averaged over the window, not the last step.
The confirmatory run was stopped before it finished. Re-run on seeds 1–9 with the same verdict rule; then the
confirmatory test above (seeds 11–19, same rule on the 10 new pairs) for any verdict that is not null.

### Re-run result (2026-11-10) and confirmation
Re-run with the fix: sex_p on vs neutral higher in 6/10, lower in 4/10 -> **no detectable selection**;
on_cost 5/10 -> none. The earlier "selected against" was the transmission artefact. Genetic diversity on < off
in 8/10 -> to confirm (same rule on the 10 new pairs, seeds 11–19, arms off and on); population, species,
mean_mut, mean_div, in_colony: no consistent sign. Off-world fingerprints still equal the F3/F4 commits.

Confirmation (seeds 11–19, arms off and on): diversity on < off in 6/10 -> **not confirmed**. F5a verdict: null
on every pre-registered question.

### F5a addendum: sensitivity check (fixed before running, 2026-11-10)
The `sex_cost=1` arm did not show selection against sex either, so the assay may be blind. Positive control:
arm `on_cost4` (`sex_cost=4`, just below `div_min - body_cost` = 5 so the affordability guard does not skip
mating), seeds 1–9, both planets, compared with the existing neutral rows. Expectation: sex_p lower than
neutral in >= 8/10. If it fires, the assay can detect a cost of that size; if not, every F5a null is
inconclusive.

Result: lower than neutral in 6/10 (median 0.37 vs 0.50) -> the positive control **did not fire**; every F5a
null is inconclusive.


## P1 Experiment power (closed 2026-11-10)

### Checklist
1. [x] P1 design: calibrate experiment power on a positive control before re-asking open questions
2. [x] `--immigration` option in the F4/F5 experiment scripts
3. [x] Calibration: positive control (`sex_cost=4` vs neutral) under longer runs and no immigration
4. [x] Re-ask F5a (sex at cost 0) at the cheapest setting where the control fires
5. [x] Docs (ROADMAP methods note, F5a section), CHANGELOG, TEST.md; local commit; ask before pushing

### Why (item 1)
F3, F4 and F5a ended with weak or null results, and F5a's pre-registered positive control (a mating cost of 80%
of a body) was not detected at the standard setting (10k steps, immigration 0.5, 10 planet x seed pairs).
A null from an assay that cannot see a known effect is not a result. Fix the assay first, one lever at a time,
and measure each lever on a known effect. The machine has 32 cores, so seeds are cheap in wall-clock time.

### Calibration (item 3), fixed before running
Positive control: arm `on_cost4` vs `neutral`, both planets (flat day/night + seasons, `volcanic.json`),
**10 seeds each (1, 3, …, 19) = 20 pairs**. Measured on the second half of each run, descendants only.
Settings:
- **A** immigration 0.5, 30k steps (longer runs only);
- **B** immigration 0, 30k steps (no fresh random propensities after the start);
- (reference, already known: immigration 0.5, 10k steps, 10 pairs: 6/10.)

Detection rule: the control fires if `sex_p` is lower than neutral in >= 16 of 20 pairs (sign test, two-sided
p ≈ 0.012). The cheapest setting where it fires becomes the standard; if none fires, report that and stop
before re-asking anything.

### Re-ask (item 4), fixed before running
At the chosen setting, arms `on` (cost 0) vs `neutral`, same 20 pairs: sex selected if `sex_p` higher in >= 16/20,
selected against if lower in >= 16/20, otherwise no detectable selection — now at a known sensitivity.

### Calibration result (2026-11-10)
Positive control lower than neutral: **A 16/20, B 16/20** — it fires at both settings (borderline), with a wider
gap without immigration (median `sex_p` 0.21 vs 0.49 neutral in B; 0.29 vs 0.43 in A). Reference at 10k steps
with immigration: 6/10. So run length was the missing lever; immigration 0 adds separation.
Both settings cost the same, and the rule did not say how to break a tie, so — fixed before the re-ask — the
re-ask runs at **both** A and B, and a verdict is claimed only if both settings give it (>= 16/20 each);
otherwise "no detectable selection at this sensitivity".

### Re-ask result (2026-11-10)
Sex at cost 0 higher than neutral in **8/20 (A)** and **9/20 (B)** (lower in 12 and 11; medians 0.497 vs 0.425 and
0.478 vs 0.493) -> **no detectable selection at this sensitivity** (the sensitivity that detects `sex_cost=4`).
