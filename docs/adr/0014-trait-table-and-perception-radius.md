# ADR-0014: Trait table and evolvable perception radius (save v9)

- **Status**: Accepted (2026-11-12: the owner chose "refactor first" and "the kernel refuses `sense_range` until
  the experiment validates it")
- **Date**: 2026-11-12
- **Deciders**: project owner
- **Parents**: [ADR-0011](0011-prey-defence-and-save-v8.md) (the deferred "extended genome" refactor),
  [ADR-0005](0005-sensor-genes-and-save-v3.md) (sensing), [ADR-0008](0008-engine-port-stack.md) (Rust kernel)

## Context
PLAN item 10 (the owner's proposal, 2026-11-11) adds an evolvable perception radius `sense_r`. ROADMAP F3 names
the radius-1 view as a likely reason no hunting or fleeing appears. `sense_r` cannot be a 17th gene:
`random_genes()` would draw 17 values, which changes every world's RNG stream, all golden sets and the species
distance. So it is a fifth per-cell trait outside the genome, after `sex_p`, `plast_p`, `hgt_p` and `armor_p`.

ADR-0011 deferred the "extended genome" refactor to "a fifth propensity, or M5". M5 has passed without it. Each trait is
repeated in Python, `worldsim/world.py`:
- the `Cell` constructor;
- seeding and immigration (a draw if its flag is on);
- division (`offspring_<trait>`, a mutated copy);
- `express()` (upkeep);
- `stats()`;
- the save row and its checks (`persistence.py`);
- the viewer inspector.

That is about 46 lines in `world.py` alone. The Rust kernel already groups the traits in one `Traits` struct
(`engine-rs/src/world.rs`).

The kernel ports every flag today. `sense_r` is an experiment, and its result may be null for the same reason as F3
and F5d: median life is 6-8 steps, so few cells live long enough to use what they see.

## Options considered
1. **The trait plumbing**
   - *Defer again with a 5th slot.* This copies the `armor_p` pattern once more. Rejected: a fifth copy of the
     same seven code paths, which is the drift ADR-0010 warned about.
   - *One list per cell* (`c.traits[i]`). Rejected for the hot loop: `step()` reads `c.sex_p`, `c.hgt_p`,
     `prey.armor_p` per cell and per attack. Indexing a list there is slower than a slot and harder to read.
   - *A trait table, values kept in named slots* (chosen). One module-level table, `TRAITS` (name, Config flag,
     upkeep field), drives everything generic:
     - founders' and immigrants' draws;
     - inheritance;
     - upkeep;
     - stats;
     - save checks;
     - the inspector.

     The dynamics keep reading named slots.
   - *Refactor and `sense_r` in one commit.* Rejected: the refactor's proof ("every hash unchanged") would mix
     with a new mechanism.
2. **Porting `sense_range` to the kernel**
   - *Port now.* This keeps "every flag ported" but may be thrown away if the mechanism is inert.
   - *Refuse until validated* (chosen). The kernel reads save v9 and refuses `sense_range` on, with a clear message.
     The bit-exact port becomes its own item if the experiment is positive.

## Decision
1. **Trait table (commit 1, pure refactor).** `worldsim/world.py` gains `TRAITS`, a tuple of
   `Trait(name, flag, upkeep)` in today's order: sex, plasticity, hgt, defence.
   - **Founders and immigrants** draw one `rng.random()` per trait whose flag is on, in table order: today's draws.
   - **Children** get `min(1, max(0, parent + gauss(0, mut_sigma)))` per trait whose flag is on, in table order,
     never from the mate: today's draws. No draw happens when no trait flag is on.
   - **Upkeep** in `express()` is added per trait in table order; float order is unchanged, since the plasticity diet
     setup does not touch upkeep.
   - **Cells** take `traits=` (a tuple in table order, built by `make_traits(**values)`) instead of one keyword per
     trait. The values stay in named slots.
   - **Unchanged:** the save layout (v8 still has `diet` between the traits), the state hash (it is the cross-engine
     contract, written out field by field) and the Rust kernel.
   - **`stats.csv`:** the trait means are written by one loop, so `diet_shift` moves after them in the columns.
     `plots.py` reads columns by name.
   - **Verdict:**
     - every committed golden `hashes.csv`, render and vector file is reproduced byte for byte by a full
       `g2_golden.py --all`;
     - the existing Python tests pass, adapted only to the new constructor and the single inheritance method;
     - steps/s with all flags off is within noise of before (measured, reported).
2. **`sense_r` (commit 2, the mechanism, as in PLAN item 10).**
   - **Flags:** `Config.sense_range` (off by default; acts only with `sensing` on) and a control arm,
     `sense_range_neutral`, in which the trait is inherited, mutates and costs, but the radius stays 1.
   - **The trait:** `sense_r` is the table's fifth entry, `Trait("sense_r", "sense_range", "sense_range_upkeep")`.
     It is drawn after `armor_p`.
   - **Radius:** `R = min(sense_radius_max, 1 + int(sense_r * sense_radius_max))`, where `sense_radius_max` is an
     integer bounded to [1, 5].
   - **Upkeep:** `sense_range_upkeep * (R - 1)` per step, paid in the neutral arm too. This replaces the table's
     linear upkeep for this trait.
   - **`sensed_move`:** generalised as in PLAN item 10, with sums in a fixed order and plain Python floats, so a
     later Rust port stays bit-exact.
   - **Radius 1:** with R = 1 the current code runs, identical float for float.
   - **Flag off:** no new draw; the default and volcanic `hashes.csv` stay byte-identical.
3. **Save v9 (commit 2).** Each cell row gains `sense_r` as its 16th field; v8 saves are refused, as each version
   bump has done. The Rust kernel reads v9 (`SAVE_VERSION`, `CELL_ROW_LEN`, `config.rs`, the bound checks) and
   **refuses `sense_range` on** and a non-zero `sense_r` with the flag off. The golden sets are regenerated: their
   hashes do not change (flag off), only the save bytes do. This breaks "every flag ported" explicitly. A flag-off
   world is still fully ported, and the port of `sense_range` is a later PLAN item, opened only if the experiment is
   positive.
4. **Experiment (commit 3, verdict fixed now, before any run).**
   - **Setup:** arms on, neutral and off, with `sensing=1` and immigration 0, on a flat world with day/night and on
     `volcanic.json`. P1 standard: 30k steps x 20 seed pairs.
   - **Question (1):** is `sense_r` selected? Yes if `sense_r` (or mean R) ends higher in on than in neutral in
     **>= 16/20** pairs.
   - **Question (2):** do hunting or fleeing appear? Measured by `w_danger` and by kills by mobile predators, on
     against neutral.
   - **Known risk:** short lives may make the result null, as for F3 and F5d. A second run with `defence=1` (longer
     lives) is part of the plan, not a rescue.
   - **Reporting:** a null or negative result is reported as such.

## Consequences
- A new per-cell trait is one table entry plus its effect, instead of seven edits.
- The hot loop keeps named slots; the state hash and the save layout stay explicit, because they are contracts.
- Until `sense_range` is validated and ported, Unity and the kernel cannot run a world with it on. They refuse it
  loudly, never silently.
- Risks:
  - **Bit-exactness of the refactor.** Mitigated by the full `--all` verdict.
  - **A generalised `sensed_move` that drifts at R = 1.** Mitigated by the flag-off and R = 1 identity checks.
  - **A null experiment.** Accepted, and reported honestly.
