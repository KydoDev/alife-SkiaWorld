# PLAN

G2 M5, second half: world creation and interventions in the kernel, as decided in ADR-0012 and ADR-0013 (both
accepted 2026-11-11; world creation first). Work on `main`, one commit per piece, push only with the owner's OK.
Verdicts, cases and non-vacuous conditions are fixed in the ADRs, before any run; detail: `docs/G2_PLAN.md`.

## Checklist
1. [ ] ADR-0012 piece 1: CPython integer and string seeding in `rng.rs`; raw-state golden vectors
2. [ ] ADR-0012 piece 2: numpy pairwise mean (`numpy_mean`), bit-equal to `ndarray.mean()` on the fixed lengths
3. [ ] ADR-0012 piece 3: `generate_terrain` (incl. `vent_plume`); terrain digest equal on every listed case
4. [ ] ADR-0012 piece 4: `World::new`; step-0 hashes and creation sets `create_default`, `create_volcanic`
5. [ ] ADR-0012 piece 5: `ws_world_create`, ABI 2, FFI tests, Unity "new world"; security review first
6. [ ] ADR-0013 piece 2: `refresh_terrain` refactor; all hashes and renders unchanged
7. [ ] ADR-0013 piece 3: `World::intervene` with validation; interventions golden kind; `play.replay` pytest
8. [ ] ADR-0013 piece 4: `ws_world_intervene`, `WS_ERR_INVALID`, ABI 3, FFI tests; security review first
9. [ ] ADR-0013 piece 5: Unity sandbox tools from exported `GameRules()` parameters (checked by hand)

## Rules for every piece
- **Verdict** as written in the ADR piece, fixed before the run; a failed verdict is fixed on the Rust side
  (changing Python's maths or `play.py`'s edits is the owner's decision only).
- **Existing sets**: every committed `hashes.csv` stays byte-identical (creation and interventions are off the
  load and step path).
- **Before each push**: `pytest`, `ruff check .`, `cargo fmt --check`, `cargo clippy --locked --all-targets -D warnings`,
  `cargo test --locked`. Each ABI change bumps `WS_ABI_VERSION` once, with the Unity wrapper (ADR-0012 rule).
