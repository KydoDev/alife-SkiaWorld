# Deployment Guide

Last updated: 2026-11-10

WorldSim is a public, open-source desktop/CLI project. There is no cloud
deployment and no server; "deploying" means a green `main` on GitHub
(`github.com/KydoDev/alife-SkiaWorld`).

## Environments
- **Local**: Python 3.12+, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).
- **CI**: GitHub Actions, Ubuntu, Python 3.12.

## CI/CD pipeline (`.github/workflows/ci.yml`)
Runs on every PR and on pushes to `main`:
1. **secrets** — gitleaks over full history.
2. **lint-test** — `ruff check .`, `pytest` (coverage gate in `pyproject.toml`),
   and a 300-step headless smoke run of `run.py`.

Dependabot (`.github/dependabot.yml`) opens weekly grouped updates for pip and
GitHub Actions.

Branch protection on `main` (to enable in GitHub settings): require the CI
checks, disallow force-push.

## Configuration and secrets
None required. `.env.example` lists keys if any are ever introduced.

## Releases
Non-commercial project: no formal release process yet. If the game track (G1+)
starts, adopt SemVer with a single version source and tagged releases.

## Code ↔ infra couplings
- `run.py` CLI flags used by the CI smoke run (`--steps`, `--seed`, `--out`, `--snap-every`).
- `requirements*.txt` installed by CI and by `scripts/bootstrap-dev.*`.
