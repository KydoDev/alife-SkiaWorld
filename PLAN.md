# PLAN

G2 M5: the kernel runs everything the Python engine runs (owner's request 2026-11-11, "vai con M5"). Work on `main`,
one commit per piece, push only with the owner's OK. Flags first, one at a time; planets and interventions are
design questions for later (they need an ADR). Detail of the milestone: `docs/G2_PLAN.md`.

## Checklist
1. [x] Golden infrastructure: `g2_golden.py --set KEY=VALUE`, one golden set per flag, Linux regeneration in CI
2. [x] Flag `defence` in the kernel: `armor_p`, failed-attack draw, upkeep, `defended`; golden set `defence`
3. [x] Flag `hgt` in the kernel (gene transfer during life, re-express); golden set `hgt`
4. [ ] Flag `plasticity` in the kernel (diet, acclimation); render from the diet; golden set + renders
5. [ ] Flag `sex` in the kernel (mate choice, two-parent offspring); golden set `sex`
6. [ ] Flag `sensing` in the kernel (`sensed_move`); golden set tuned so sensed moves happen
7. [ ] Flag `open_genome` in the kernel (variable-length rules, loader bounds); golden set `open_genome`
8. [ ] Combined golden sets: all ported flags on; a small world that goes extinct and reseeds with flags on
9. [ ] Design (ADR): world creation in the kernel (planet forms, images, numpy pairwise mean)
10. [ ] Design (ADR): interventions through the C ABI (write entry points, ABI version bump)

## Rules for every flag piece (fixed before any run)
- **Verdict**: no divergent step in 1000 against the golden set made on the same OS, and `hashes.csv` of the
  `default` and `volcanic` sets byte-identical (the proof that the flag draws no RNG and changes nothing when off).
- **Hash coverage**: the state hash (`scripts/g2_golden.py`, `engine-rs/src/hash.rs`) gains the flag's per-cell
  slot and counters, included only when the flag is on, so the existing hashes stay as they are.
- **Non-vacuous set**: the set records that the mechanism fired in the hashed steps (e.g. `defended > 0`, spread
  of `armor_p`); a set where nothing fires proves nothing.
- **Loader**: the flag's save fields are bounds-checked like `persistence.py` (untrusted input); refusal tests
  that used this flag as their example move to a flag still unsupported.
- **Speed**: the M3 benchmark of the default flags is re-run once after the first flag (new `Cell` field, branches).
- **Before each push**: `pytest`, `ruff check .`, `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`,
  `cargo test --locked`. The C ABI does not change for flags (no version bump, no Unity work until 9–10).

## Golden infrastructure (item 1)
- `g2_golden.py --set KEY=VALUE` (same parsing as `run.py`, recorded in `rng.json` meta) and `--all ROOT`.
- The sets are listed once, in `SETS` in the script; pytest follows it and checks that the committed directories
  and `GOLDEN_SETS` in `engine-rs/tests/common/mod.rs` match; CI regenerates the Linux sets with `--all`.
- Result: `--all` reproduces both committed sets (hashes, renders, RNG draws equal; saves equal uncompressed).
