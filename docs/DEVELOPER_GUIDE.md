# Developer Guide

Last updated: 2026-11-10

**`./scripts/bootstrap-dev.ps1` (Windows) or `./scripts/bootstrap-dev.sh` — run once per clone.**

## What the bootstrap does
1. `git config core.hooksPath .githooks` — enables the committed hooks:
   `pre-commit` (secret scan) and `post-commit` (background knowledge-graph refresh).
   Git hooks do not survive a clone; this line is what makes them real.
2. `pip install -r requirements.txt -r requirements-dev.txt`.
3. `pre-commit install` if the `pre-commit` framework is available (gitleaks,
   ruff, whitespace checks); otherwise the hook's inline fallback scan runs.
4. Builds the Graphify knowledge graph if `graphify-out/graph.json` is missing
   (`--code-only` unless an LLM API key is set).

## One-off machine installs
- Python 3.12+.
- `pip install pre-commit` — full secret scanning and linting on commit.
- `uv tool install graphifyy` then `graphify install` — knowledge graph used by
  AI agents to orient cheaply in the codebase (optional; agents fall back to search).

## Secrets
WorldSim needs none today. If a key is ever needed, add it empty to
`.env.example` and put the real value in `.env` (git-ignored).

## Running
```bash
python view.py                                                 # interactive viewer
python run.py --steps 10000 --seed 1 --out runs/test1          # headless run
python run.py --steps 5000 --out runs/test2 --set pred_eff=0.7 # override any Config field
python run.py --steps 5000 --seed 1 --out runs/a --save-every 1000         # periodic saves
python run.py --resume runs/a/world_003000.json.gz --steps 2000 --out runs/b  # continue a save
python view.py --load runs/a/world_final.json.gz                           # open a save
python run.py --planet examples/volcanic.json --steps 5000 --out runs/v   # planet from a form
python view.py --planet examples/planet.png                               # planet from an image
```
A run writes `config.json`, `stats.csv`, `snap_*.png`, `world_final.json.gz`
(+ `world_NNNNNN.json.gz`), `stats.png`, and with species tracking (default;
`--no-species` to disable) `species.csv`, `species_tree.png`, `novelty.png`.
Species parameters (`species_threshold`, `novelty_activity`, `species_prune_peak`)
only change the analysis, never the simulation. Every `Config` is range-checked
(`Config.validate()`); environment fields: `day_length`, `day_amplitude`,
`year_length`, `season_amplitude`, `rock_fraction`, `vent_count`, `vent_strength`,
`vent_radius`, `chemo_gain`. A planet form is JSON with `star` (`red_dwarf`, `sun`,
`blue_giant`), `day_night`, `seasonality`, `ocean_depth`, `seabed_relief`,
`volcanism`, `mineral_richness`, optional `seed`, `name` and `config` overrides —
see `examples/`.
Viewer keys: `SPACE` pause · `N` one step · `+/-` speed · `O` organic matter ·
`S` snapshot · `R` new world · click = inspect a cell.

## Tests and lint
```bash
pytest                                   # full suite, coverage gate from pyproject.toml
pytest tests/test_world.py::test_name    # single test
ruff check .                             # lint
```
See [TEST_STRATEGY.md](TEST_STRATEGY.md). Record results in `TEST.md` (archive
the previous content into `test_history.md` first).

## Experiments
A new mechanism lands with an experiment: the `run.py` command, the seed(s),
and the outcome, recorded in the relevant design doc or ROADMAP phase. Compare
the same seed before and after a change.

## Standards and conventions
[`CLAUDE.md`](../CLAUDE.md) is the authority. In short: English for all new
code/docs, every tunable in `Config`, all randomness through `World.rng`,
Conventional Commits (`feat(engine): ...`), small PRs into a protected `main`
(CI must pass, no force-push — branch protection should be enabled on GitHub).

Target: a new contributor goes from clone to a running viewer in under 30
minutes following only this document.
