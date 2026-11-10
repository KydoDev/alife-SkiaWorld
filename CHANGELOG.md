# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); commits follow Conventional Commits.

## [Unreleased]

### Added
- Project governance (init-skia-project v1.5.0): `CLAUDE.md`, `.agents/AGENTS.md`,
  Claude subagents in `.claude/agents/` (senior-architect, code-review-security,
  qa-specialist, doc-keeper, product-manager, simulation-dev).
- Repository safety: `.gitattributes`, extended `.gitignore`, committed
  `.githooks/` (secret-scan pre-commit, graph-refresh post-commit),
  `.pre-commit-config.yaml`, `.env.example`, `scripts/bootstrap-dev.ps1`/`.sh`.
- CI (`.github/workflows/ci.yml`: gitleaks, ruff, pytest with coverage gate,
  headless smoke run) and Dependabot.
- pytest suite of engine invariants (`tests/test_world.py`), `pyproject.toml`
  (pytest, coverage, ruff), `requirements-dev.txt`.
- Docs: `INDEX`, `ARCHITECTURE`, `DEVELOPER_GUIDE`, `TEST_STRATEGY`,
  `DEPLOYMENT_GUIDE`, ADR-0001; `TEST.md`, `test_history.md`.
- Graphify knowledge graph setup (`.graphifyignore`; output git-ignored).

### Changed
- Research and design docs translated to English and renamed
  (`state-of-the-art.md`, `theory.md`, `ROADMAP.md`); README translated.
- ROADMAP: v0 marked done, F1 in progress, per-phase status lines.

- Viewer panel, `run.py` console output and plot labels, CLI help, and all code
  comments/docstrings translated to English.

### Fixed
- Viewer: window height now fits the full cell inspector panel; the last gene
  line (`mut`) was cut off at the default 64-row world size.
- Determinism per seed: `Cell` now hashes by its seed-deterministic `id`, so
  the iteration order of `bonds` sets (colony energy sharing) no longer depends
  on memory addresses. Same seed now gives byte-identical `stats.csv`.
- Removed unused `math` import in `worldsim/world.py`.

## [0.1.0] - 2026-11
- v0: base engine, pygame viewer, headless runner, research/design docs.
