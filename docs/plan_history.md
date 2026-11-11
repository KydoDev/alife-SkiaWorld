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


## F5b Diet plasticity (closed 2026-11-10)

### Checklist
1. [x] F5b design: within-life diet plasticity with an evolvable rate; verdict rules fixed below before running
2. [x] Engine: `plasticity` flag, `Cell.plast_p` + acclimated diet, upkeep, neutral arm; off-world bit-identical
3. [x] Save format v6 (plast_p, diet), viewer inspector line, stats `plast_p_mean` / `diet_shift`
4. [x] Tests: no plasticity code runs when off, fingerprints vs c3e1c43, loader validation, resume, bookkeeping
5. [x] `scripts/f5b_experiment.py`; positive control first, then the question (P1 standard)
6. [x] ADR-0009, ROADMAP F5b, ARCHITECTURE, USER_MANUAL, CHANGELOG, TEST.md; local commit; ask before pushing

### Mechanism (item 1)
Roadmap: "during life some traits adjust to the environment (e.g. more photosynthesis if there is light), without
changing the DNA". One mechanism: **diet acclimation**. Not included (separate mechanisms, later): passing the
acclimated state to the offspring (epigenetic inheritance), Lamarckism.

- With `plasticity` on, each cell carries `plast_p` in [0, 1] (not a gene: stored like F5a `sex_p`, exists and
  draws RNG only when the flag is on). Seeded cells and immigrants draw it at random; children inherit it from
  the dividing parent, mutated with its `mut_sigma`.
- The predation share stays genetic. The non-predatory share is split among photo / sapro / chemo by an
  acclimated `diet` (3 proportions). At birth `diet` = the genetic proportions (no transgenerational effect).
- Each step, before feeding, the cell reads what each diet would yield on its tile at full specialisation
  (`photo_gain x light`, `sapro_eff x min(organic, sapro_rate)`, `chemo_gain x chem`), normalises to proportions
  `t`, and moves `diet += plast_p x plastic_rate x (t - diet)`. Shares and `*_k` are re-derived. Deterministic,
  no RNG. If all yields are 0 the diet does not move.
- Lag: `plastic_rate` 0.05 -> time constant >= 20 steps (a day is 200, a life up to 600).
- Cost: `plastic_upkeep x plast_p` per step (default 0.05, a quarter of `base_cost` at plast_p = 1).
- `plastic_neutral`: control arm, `plast_p` inherited and mutated, diet never moves; it pays `plastic_upkeep`
  as configured (so the drift baseline uses `plastic_upkeep=0`, the positive control a large cost).

### Experiment (item 5), fixed before running
P1 standard: 30k steps, measured on the second half, descendants only. **Immigration 0** (setting B, chosen in
advance: widest separation in P1). Planets with day/night: flat with day/night + seasons, `volcanic.json`;
seeds 1, 3, ..., 19 -> 20 pairs. Sensing, open genome and sex off.
Arms: `off`; `on` (default cost 0.05); `neutral` (neutral, cost 0); `control` (neutral, cost 0.2).

1. **Positive control first**: `plast_p` in `control` lower than `neutral` in >= 16/20 pairs. If it does not
   fire, report the assay as blind for this trait and stop before claiming anything.
2. **Question**: `plast_p` in `on` vs `neutral`: selected if higher in >= 16/20, selected against if lower in
   >= 16/20, otherwise no detectable selection (at the control's sensitivity).
3. **Mechanism check** (reported, no verdict): mean |diet - genetic diet| of descendants in `on`, so that a
   null cannot mean "it never moved".
4. **Contrast** (exploratory, 10 pairs, flat world with constant light, seeds 1-19 odd): prediction written now —
   plasticity is favoured less there than on the day/night planets (fewer pairs higher than neutral).
5. **Consequences** `on` vs `off` (population, diversity, species): a claim only at >= 16/20.

### Result (2026-11-10)
Positive control 20/20 (fires). `plast_p` on > neutral in 13/20 (lower 7) -> no detectable selection. Diet shift in
`on` median 0.25 (0.16-0.31). Contrast: on > neutral 2/10 under constant light vs 13/20 with day/night (predicted
direction). Consequences on vs off: 9-15/20, no claim. Per planet: flat day/night 8/10, volcanic 5/10.


### F5b addendum: review fixes and re-run (closed 2026-11-10)

#### Checklist
1. [x] F5b implemented, tested and run once (closed items in docs/plan_history.md, "F5b Diet plasticity")
2. [x] Review fixes: no-feeding-gene cell fed as a generalist under plasticity; loader accepts a frozen diet that moved
3. [x] Re-run the whole F5b experiment on the fixed code, with a cost-matched neutral arm (rules below)
4. [x] Rewrite the F5b results in ROADMAP, CHANGELOG, TEST.md, plan_history; local commit; ask before pushing

#### Why (items 2-3)
The review found that a cell with all four feeding genes at 0 was fed as a 1/3 generalist when plasticity was on
(it cannot feed with plasticity off). Rare, but it touches every plasticity arm, so the first run is superseded.
The review also noted that `on` vs `neutral` mixes the benefit of acclimation with its cost (on pays 0.05 x plast_p,
neutral pays nothing), and that the positive control's cost (0.2) is four times the `on` arm's.

#### Re-run rules, fixed before running (written while the run was in progress, before any result was seen)
Same setting, seeds, planets, contrast and rules 1-5 as before (plan_history). New arm `neutral_cost`: neutral with
the default `plastic_upkeep` 0.05 (pays exactly what `on` pays, no effect).
6. **Acclimation effect, cost-matched**: `plast_p` on vs neutral_cost: beneficial if higher in >= 16/20, harmful if
   lower in >= 16/20, otherwise no detectable effect.
7. **Power at the real cost**: `plast_p` neutral_cost < neutral in >= 16/20 means the assay detects a cost of the size
   plasticity pays; if not, a null in rule 6 is only bounded by the 0.2 control.

#### Re-run result (2026-11-10)
Control 20/20 (fires). on vs neutral_cost: higher 19/20 -> **acclimation beneficial**. on vs neutral: 14/20 -> no
detectable net selection. neutral_cost < neutral: 15/20 -> the 0.05 cost alone is not detected. Contrast 2/10.
Population on > off 16/20 (rule 5: higher; not confirmed on new seeds). Diet shift median 0.26.

---

### F5c Horizontal gene transfer (closed 2026-11-10)

F5c Horizontal gene transfer (third F5 mechanism). G2 engine port runs in parallel: see docs/G2_PLAN.md
(session g2-m1c-m2); the default dynamics stay frozen, the save bump below regenerates the golden sets.

## Checklist
1. [x] F5c design and pre-registered verdict rules (this file); ADR-0010
2. [x] Engine: `Config.hgt*`, `Cell.hgt_p`, transfer in `step()`, stats; no RNG when off
3. [x] Save v7 (`hgt_p` per cell, `hgt_events` counter); golden sets regenerated, Rust `SAVE_VERSION = 7`
4. [x] Tests: off-world untouched, transfer semantics, neutral arm, bit-exact resume, loader validation
5. [x] Off-world fingerprints equal to `367aecd` (6 configurations); speed off/on
6. [x] Experiment `scripts/f5c_experiment.py`, 30k steps, 20 pairs; verdict per the rules below
7. [x] Review (code-review-security), docs (ROADMAP, ARCHITECTURE, CLAUDE.md, USER_MANUAL, CHANGELOG, TEST.md)

## Design
- **Source: living neighbours** (conjugation-like). A per-tile gene pool in the organic field (transformation)
  would add a large save field; it is a later, separate experiment.
- **What moves: one fixed gene.** The recipient copies the value of one random locus (of the 16 fixed genes)
  from a random neighbour (Moore neighbourhood, bonded or not, any lineage, no genetic-distance filter: that is
  the difference from F5a mating). Rules, `sex_p`, `plast_p` and `hgt_p` itself are not transferred.
- **When:** at the start of the cell's turn, before feeding: with probability `hgt_p x hgt_rate` (one
  `rand()` per living cell per step, only in the active arm). The genome changes for life and is inherited,
  so the phenotype is re-expressed (`express`); with plasticity on that resets the diet to the genetic split.
- **Evolvable propensity `hgt_p`** in [0, 1], outside the genome (like `sex_p`, `plast_p`): seeded cells and
  immigrants draw it at random (after the `plast_p` draw), children inherit the dividing parent's, mutated
  with its `mut_sigma`.
- **Cost:** `hgt_upkeep x hgt_p` per step (default 0.05), paid in the neutral arm too.
- **Neutral arm** `hgt_neutral`: `hgt_p` inherited and mutated, cost paid, no transfer, no draw.
- **Observer stats:** `hgt_p_mean`, `hgt_events` (cumulative counter, saved), `hgt_foreign` (cumulative
  transfers whose donor has another lineage; saved). Species stay as assigned at birth (tracker unchanged).
- Default `hgt_rate` **0.1**, set from the probe below (at `hgt_p` 0.5, ~0.85 transfers per mean lifetime).

## Probe (before coding; existing engine, seeds 41 and 43, 10k steps, second half, immigration 0)
`scratchpad f5c_probe.py`; flat day/night + seasons and `volcanic.json`, 4 runs:
- **Mean lifespan ~16–18 steps** (population / deaths per step), not the 600-step maximum: most cells die
  young, so a rate of 0.01 would give < 0.1 transfers per life. Hence `hgt_rate` 0.1.
- 92–97% of cells have a neighbour (a donor is almost always there).
- |gene difference| to a random neighbour at a random locus: **median 0.010, about one mutation step**
  (`mut_sigma` ≈ 0.010–0.011); mean 0.03 (a tail of divergent donors). Foreign-lineage donors 0–9%.
- So with immigration 0 a transfer is mostly one extra mutation-sized change at one of 16 loci (6 of them,
  the sensor weights, inert with sensing off). **A null here is likely and is worded "mechanism nearly inert
  in this world (donors are near-clones)", not "horizontal transfer is not selected".**

## Experiment (P1 standard, rules fixed before any run)
Immigration 0; flat world with day/night + seasons, and `examples/volcanic.json`; seeds 1, 3, ..., 19 = 20
pairs; 30k steps; second half, sampled every 10 steps; descendants only (`id != lineage`, as F5b). Arms: off /
on / neutral (cost 0) / neutral_cost (cost = default) / control (neutral, cost 0.2). The metric is the mean
`hgt_p` of descendants over the second half.
1. **Positive control**: `hgt_p` control < neutral in ≥ 16/20, else the experiment cannot see a cost this
   size and no selection verdict is given.
2. **Is transfer itself favoured?** `hgt_p` on vs neutral_cost (same cost, no effect): higher in ≥ 16/20 →
   beneficial; lower in ≥ 16/20 → harmful; otherwise no detectable selection.
3. **Net selection**: on vs neutral (no cost), same thresholds.
4. **Mechanism check** (reported, not a verdict): transfers per birth (`hgt_events / births`, second half),
   foreign-donor share (`hgt_foreign / hgt_events`), and the expected |change| per transfer measured as in
   the probe (random neighbour, random locus, sampled); 0 events in the neutral arms.
5. **Population, lineages, species** on vs off: a direction is claimed only at ≥ 16/20, as exploratory.
6. **Power at the real cost**: neutral_cost < neutral in ≥ 16/20 → the assay detects the default cost.
7. **Contrast with divergent donors** (exploratory, 10 pairs): flat day/night world with immigration 0.5
   (random-gene immigrants), arms on / neutral_cost. Prediction: larger |change| and foreign share than in
   the main runs, and `hgt_p` on < neutral_cost in more pairs than in the main runs (foreign genes are
   mostly maladapted, so transfer is pushed down). Reported as a count, no verdict.
8. A verdict at exactly 16/20 is reported as "at the threshold, not confirmed on new seeds".

#### Result (2026-11-10)
Control 20/20 (fires). on vs neutral_cost 10/20 -> no detectable effect of transfer. on vs neutral lower 16/20 ->
selected against, at the threshold; confirmation on seeds 21-39 lower 18/20. neutral_cost < neutral 15/20
(18/20 in the confirmation). 0.48 transfers per birth, foreign share median 0: mechanism nearly inert here. Contrast
5/10 (foreign share only 5%). Species on > off 16/20 (16/20 confirmation; post hoc 18-19/20 vs neutral_cost: from the
transfer, cause untested). Diversity lower 17/20 (16/20); the cost alone 15/20 and 14/20, so not attributed.
Population no consistent sign.

---

### F3 re-run at the P1 standard (closed 2026-11-10)

F3 re-run at the P1 standard: is phototaxis selected? This comes before F5d learning, whose probe found nothing to
learn from (below). No engine, save or Rust change: an experiment only.

## Checklist
1. [x] F5d probe: learning on the F3 sensor weights is nearly inert in this world (recorded below)
2. [x] Design and pre-registered verdict rules (this file), written before any run
3. [x] Script `scripts/f3_p1_experiment.py`, smoke test
4. [x] Run 30k steps x 20 pairs; verdict per the rules below
5. [x] Docs (ROADMAP F3 + F5 status, CHANGELOG, TEST.md), commit on `exp/f3-p1`

## F5d probe (2026-11-10, before any F5d code)
Sensing on, immigration 0, flat day/night + seasons and `volcanic.json`, seeds 41 and 43, deaths of descendants in
steps 5-10k (scratchpad `f5d_probe.py`): median life 6-8 steps; 18-41% of cells ever make a sensed move; 0.4-2.5
sensed moves per life; sensed moves are 3-12% of cell-steps; cells living >= 30 steps (a proxy for the ones that
reproduce: parents are not recorded) make a median of 0-2. A weight that learns from one or two experiences cannot
learn, so F5d as specified ("the F3 brain changes its weights during life") would be inert by construction.
Recorded as "precondition not met in this world"; the owner chose to re-run F3 at P1 first.

## Why a re-run
The F3 verdict ("phototaxis likely selected, modest effect") rests on 10k steps, 2 seeds and the immigration arms.
P1 showed that 10k-step nulls and leans are not reliable; the P1 standard is 30k steps, immigration 0, 20 pairs and
a positive control.

## Design (rules fixed before any run)
Immigration 0; flat world with day/night + seasons (`day_amplitude=1`, `season_amplitude=0.5`) and
`examples/volcanic.json`; seeds 1, 3, ..., 19 = 20 planet x seed pairs; 30k steps; second half, sampled every 10
steps; descendants only (`id != lineage`). Weights as `2g - 1` in [-1, 1].
Arms:
- **off**: sensing off (the sensor genes are inert: drift baseline, no cost);
- **free**: sensing on, `sense_upkeep=0` (directed movement, no cost: the cost pushes |w| to 0 and would confound
  the sign of `w_light` against the off arm);
- **on**: sensing on, default `sense_upkeep` 0.05 (reported);
- **control**: sensing on, `sense_upkeep=0.5` (positive control).

Primary metric: mean `w_light` over **all descendants** (the gene is inherited by every cell, but acts only in
unbonded movers; with immigration 0 only 0-1.3% of cells are motile, too few for a primary metric).
1. **Positive control**: mean |`w_light`| control < free in >= 16/20, else the assay is blind and no verdict on
   rule 2 is given.
2. **Phototaxis**: mean `w_light` free > off in >= 16/20 -> selected towards light; free < off in >= 16/20 ->
   selected away from light; otherwise no detectable selection.
3. Secondary: the same comparison on motile unbonded descendants (`move` > 0.3), only on pairs where both arms have
   >= 10 motile descendants per sample on average; reported with the number of usable pairs, no verdict below 16
   usable pairs.
4. Exploratory: the other five weights free vs off (counts only; five comparisons, so a single 16/20 is not
   claimed), and `w_light` on vs off.
5. Exploratory: population, species, share of motile cells, free vs off.
6. A count of exactly 16/20 is reported as "at the threshold, not confirmed on new seeds".

## Result of the main run (2026-11-10)
Control 16/20 (fires, at the threshold). Phototaxis free vs off: higher 13/20 -> no detectable selection
(free median 0.40, off -0.08). Motile descendants: 1 usable pair (median 2.6 motile cells per sample in free), no
verdict. Not pre-registered: flat 9/10 higher, volcanic 4/10. Re-running `flat_seasons` seed 1 `free` on main
after #19 (libm light) gave an identical row.

## Confirmation (rules fixed before running; seeds 21, 23, ..., 39; arms off, free, control)
C1. Control |w_light| control < free in >= 16/20: the assay's power is confirmed; otherwise the main null is only
    "blind at a 0.5 cost".
C2. Phototaxis free vs off: reported as a count; a verdict only at >= 16/20 in the confirmation itself.
C3. Post-hoc lean from the main run: free > off on `flat_seasons` in >= 8/10 of the new seeds -> "flat lean
    reproduced" (exploratory); otherwise it is not kept.

## Confirmation result (2026-11-10)
C1 control 19/20 -> power confirmed. C2 phototaxis free vs off 16/20 (at the threshold; median +0.45 vs +0.05).
C3 flat 9/10 -> flat lean reproduced (exploratory). Volcanic 7/10. Motile descendants: 1 usable pair.
Reading: a lean towards light, not established (13/20 then 16/20).

---

### World study: predation pressure (closed 2026-11-11)

World study: find settings where cells live long enough for within-life mechanisms (learning, regulation,
differentiation) to have something to act on. A parameter study, not a new mechanism: the default world is not
changed; the result is a named set of overrides for later experiments.

## Checklist
1. [x] Death probe: 96-97% of deaths are predation (below)
2. [x] Goal and selection criteria (this file), written before the sweep
3. [x] Coarse sweep of predation pressure, 10k steps, seeds 41 and 43, both planets
7. [x] Extended sweep with spec_exp (rules below), same criteria
4. [x] Pick a setting by the criteria; check it at 30k steps on 20 pairs
5. [x] Re-run the regulator pilot (not run: no world accepted) in the chosen world
6. [x] Docs (ROADMAP, CHANGELOG, TEST.md), commit, ask to push

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

## Check of the chosen setting (owner decision 2026-11-11; criteria fixed before running)
Setting: `spec_exp=3`, `pred_eff=0.25`, `pred_upkeep=1.0`. **The predator criterion is relaxed after seeing the sweep
data** (from >= 2% of cells to "predators present"); this is recorded as a post-hoc change. 30k steps, the 20 P1 pairs
(seeds 1, 3, ..., 19 x both planets; independent of the selection seeds 41 and 43), second half.
Accepted as the "long-life world" if, in >= 16/20 pairs: median age at death of descendants >= 20; mean population
>= 300; no extinction; mean predator share > 0. Default-world rows on the same pairs are run alongside for reference.

## Check result (2026-11-11, `docs/world_study_check.csv`)
**Rejected: 7/20 pairs pass (needed 16).** Over 30k steps predation comes back: predator share median 4.7% (0.1-9.3%,
vs 0.5-1.8% at 10k), kills 82% of deaths, median life 15.5 (3-86; 2x the default world's 7.5, 5-9, which passes
0/20), one extinction. The 10k selection did not hold at 30k. Conclusion: with the existing parameters there is no
stable world where cells live long enough; predation re-evolves. Study closed; the default world is unchanged.

---

### F5e Prey defence (closed 2026-11-11)

F5e Prey defence (owner's choice 2026-11-11, after the world study). Goal: a world where cells live long enough for
within-life mechanisms (learning, regulation, differentiation). Branch `feat/f5e-prey-defence` off `36b4d21`; PR #21
(F3 P1) and `exp/world-study` touch the same docs and are merged before this one.

1. [x] Pilot (throwaway engine, 30k, seeds 41/43): strength 0.8 / upkeep 0.2 passes 3/4 runs (below)
2. [x] Design and pre-registered rules (this file); ADR-0011
3. [x] Engine: `Config.defence*`, `Cell.armor_p`, failed attacks in predation, stats; no RNG when off
4. [x] Save v8 (`armor_p` per cell, `defended` counter); Rust loader v8, golden sets regenerated
5. [x] Tests; off-world fingerprints equal to `36b4d21` (8 configurations); speed off/on
6. [x] Experiment `scripts/f5e_experiment.py`, 30k steps, 20 pairs; verdict per the rules below
7. [x] Review (code-review-security), docs (ROADMAP, ARCHITECTURE, CLAUDE.md, USER_MANUAL, CHANGELOG, TEST.md)

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

## Result (2026-11-11)
Primary 15/20: not a long-life world by the rule (median life < 20 in 5 pairs, 4 of them volcanic with 10-20%
predators late; one flat run with 2 extinctions). Control fires 20/20; armour beneficial 20/20, selected 19/20;
median life 28 vs 7.5 (off), longer in 20/20; kills per death lower 20/20; population higher than neutral_cost
18/20; predator share no consistent sign. Review (code-review-security): no blocking issues; added tests for
energy on a repelled attack and no predation draw in the neutral arm. Details in ROADMAP F5e.
