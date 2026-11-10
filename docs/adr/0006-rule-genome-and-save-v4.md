# ADR-0006: Variable-length rule genome and save format v4

- **Status**: Accepted
- **Date**: 2026-11-10
- **Deciders**: project owner

## Context
F4 moves from a fixed genome to one whose length evolution decides (ROADMAP, "When to increase the number of
genes?", level 2: *if I perceive X then I do Y with intensity Z*). Choices that are expensive to reverse:

1. The encoding of a variable gene, and what it can act on.
2. How it varies (duplication, the main source of new functions in nature, needs something to copy).
3. Whether it changes the existing world: F2 and F3 each shifted every seed's random stream and forced a
   recalibration of the G1 milestones.
4. What it does to the species definition (ADR-0003, ADR-0005), whose novelty count is the F1 metric. If
   longer genomes alone raised novelty, the metric would report growth as invention.

The roadmap's entry criterion ("the system stalls even in a variable environment") was not shown: F2 found
novelty rising under variable light, and F3's behavioural result is modest. The owner chose to start F4 on
2026-11-10; this ADR records that the criterion was waived, not met.

## Options considered
- **Trait tokens** (`(trait, value)` genes summed per trait): simple dosage effects, but no new behaviour.
- **Conditional rules** with a fixed vocabulary of conditions and targets: new state-dependent behaviours
  (e.g. seek light only when dark, divide later when energy is low), the number and combination of rules
  open; the vocabulary itself closed.
- **A neural network or regulatory network**: more expressive, but many weights per cell in the Python hot
  loop, and hard to read back. Level 3 of the roadmap, a later phase.
- **Species**: extend the distance to rules (needs an alignment of variable lists and a new threshold), or keep
  species on the fixed genes and measure rule innovation separately.

## Decision
- The 16 fixed genes are unchanged. A cell also has `rules`: a list of rule genes, each 4 values in [0, 1]:
  condition (always · own energy above / below a threshold · light at its tile above / below a threshold),
  threshold, target (one of the 6 sensor weights, or the division threshold), intensity `2v − 1`.
  Energy is normalised by `div_max`, light by `light_max`.
- While its condition holds, a rule adds its intensity to the sensor weight (rules stack: a duplicated rule
  doubles the effect) or shifts the division threshold by `intensity × rule_div_shift × (div_max − div_min)`,
  clamped to `[div_min, div_max]`. Conditions read only the cell's own state, so the active rules are
  collapsed once per cell per step; movement rules act only with `sensing` on.
- At division, only with `open_genome` on: point mutation of every value with the cell's `mut_sigma`, then
  one duplication (`rule_dup_rate`, the copy next to the original), one deletion (`rule_del_rate`) and one
  random new rule (`rule_new_rate`), within `max_rules`. Seeded cells and immigrants start with no rules.
- Each rule costs `rule_upkeep` per step, so genomes do not grow for free.
- `rules_neutral` is a control arm: rules exist, vary and cost the same but have no effect.
- `open_genome` is **off by default** and then draws no random numbers: the default and F3 worlds are
  bit-identical to the F3 commit (tested, and checked against two arms of the F3 experiment).
- Species stay defined on the 16 fixed genes (tracker unchanged). Rule innovation is measured separately
  (rule count, rule-type frequencies against the neutral arm).
- **Save format v4**: each cell row gains its rules. The loader accepts at most `max_rules` rules (none when
  the open genome is off), each of exactly 4 finite values in [0, 1]. v3 saves are rejected.

## Consequences
- No recalibration of G1: the game runs with the open genome off.
- The tracker is blind to rule innovations: two cells with identical fixed genes and different rules are the
  same species. Novelty numbers stay comparable with F3; rule innovation has its own measures.
- The vocabulary is closed: evolution can combine and dose rules, not invent new kinds of condition or target.
  Adding one is an append to `RULE_CONDITIONS` / `RULE_TARGETS`, which changes the decoding of existing rules
  and therefore needs a new save version.
- Per unit of weight a rule costs about the same as a sensor gene (`rule_upkeep` 0.01 per ±1, against
  `sense_upkeep / 6` ≈ 0.008 for a gene at ±1), but rules stack beyond ±1. That dosage is intended (a
  duplicated rule doubles its effect); the cap and the per-rule cost bound it.
- The condition scales are approximate: energy / `div_max` can exceed 1 in cells that cannot divide, and
  light / `light_max` reaches about 2 at midday with a full day cycle, so high `light>` thresholds act as
  "daytime". Rules are evaluated once per step, after feeding and before predation, movement and sharing.
- A regulatory network (level 3, prerequisite for F6 differentiation) can grow from the same list by letting
  rules read other rules' outputs.
