# PLAN

F3 re-run at the P1 standard: is phototaxis selected? This comes before F5d learning, whose probe found nothing to
learn from (below). No engine, save or Rust change: an experiment only.

## Checklist
1. [x] F5d probe: learning on the F3 sensor weights is nearly inert in this world (recorded below)
2. [x] Design and pre-registered verdict rules (this file), written before any run
3. [x] Script `scripts/f3_p1_experiment.py`, smoke test
4. [~] Run 30k steps x 20 pairs; verdict per the rules below
5. [ ] Docs (ROADMAP F3 + F5 status, CHANGELOG, TEST.md), commit on `exp/f3-p1`

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
