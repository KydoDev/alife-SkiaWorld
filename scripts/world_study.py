"""World study: which predation pressure lets cells live long enough for within-life mechanisms?

Grid over pred_eff x pred_upkeep, immigration 0, flat day/night + seasons and examples/volcanic.json, measured over
the second half. Per run: median age at death of descendants, mean population, predator share, killed share of
deaths, share of cells in colonies of >= 4, extinctions. Selection criteria are in PLAN.md (fixed before running).

    python scripts/world_study.py --steps 10000 --seeds 41 43
    python scripts/world_study.py --steps 10000 --spec-exp 3 4 --pred-upkeep 0.3 1.0 --out docs/world_study_spec.csv
    python scripts/world_study.py --steps 30000 --grid 0.35:0.6:3 --seeds 1 3 ... --out docs/world_study_check.csv
"""
import argparse
import csv
import itertools
import statistics as st
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worldsim import Config, World  # noqa: E402
from worldsim.worldgen import load_planet  # noqa: E402

PLANETS = ["flat_seasons", "examples/volcanic.json"]
PRED_EFF = [0.5, 0.35, 0.25]
PRED_UPKEEP = [0.3, 0.6, 1.0]
SPEC_EXP = [2.0]
SAMPLE_EVERY = 100


def make_world(planet, seed, pred_eff, pred_upkeep, spec_exp):
    base = Config().apply_overrides([
        "immigration_rate=0", f"pred_eff={pred_eff}", f"pred_upkeep={pred_upkeep}", f"spec_exp={spec_exp}"])
    if planet == "flat_seasons":
        return World(base.apply_overrides(["day_amplitude=1", "season_amplitude=0.5"]).validate(), seed=seed)
    cfg, terrain, seed = load_planet(planet, base, seed)
    return World(cfg, seed=seed, terrain=terrain)


def colony_cells(cells, min_size=4):
    """Cells in connected bond components of at least `min_size` cells."""
    seen, n = set(), 0
    for c in cells:
        if c.id in seen or not c.bonds:
            continue
        stack, size = [c], 0
        seen.add(c.id)
        while stack:
            x = stack.pop()
            size += 1
            for b in x.bonds:
                if b.id not in seen:
                    seen.add(b.id)
                    stack.append(b)
        if size >= min_size:
            n += size
    return n


def run(job):
    planet, seed, pred_eff, pred_upkeep, spec_exp, steps = job
    w = make_world(planet, seed, pred_eff, pred_upkeep, spec_exp)
    half = steps // 2
    ages, pops, pred_share, colony_share = [], [], [], []
    deaths0 = kills0 = 0
    for t in range(steps):
        if t == half:
            deaths0, kills0 = w.deaths, w.kills
        before = {c.id: c for c in w.cells} if t >= half else None
        w.step()
        if before is None:
            continue
        alive = {c.id for c in w.cells}
        ages += [c.age for i, c in before.items() if i not in alive and c.id != c.lineage]
        if t % SAMPLE_EVERY == 0 and w.cells:
            n = len(w.cells)
            pops.append(n)
            pred_share.append(sum(c.strategy == "pred" for c in w.cells) / n)
            colony_share.append(colony_cells(w.cells) / n)
    deaths = w.deaths - deaths0
    return {"planet": Path(planet).stem, "seed": seed, "pred_eff": pred_eff, "pred_upkeep": pred_upkeep,
            "spec_exp": spec_exp,
            "median_life": st.median(ages) if ages else "", "mean_life": round(st.mean(ages), 1) if ages else "",
            "population": round(st.mean(pops), 1) if pops else 0,
            "pred_share": round(st.mean(pred_share), 4) if pred_share else 0,
            "killed_share": round((w.kills - kills0) / deaths, 3) if deaths else "",
            "colony4_share": round(st.mean(colony_share), 3) if colony_share else 0,
            "extinctions": w.extinctions}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--steps", type=int, default=10000)
    p.add_argument("--seeds", type=int, nargs="+", default=[41, 43])
    p.add_argument("--planets", nargs="+", default=PLANETS)
    p.add_argument("--grid", nargs="+", default=None,
                   help="pred_eff:pred_upkeep[:spec_exp] settings (default: the full grid)")
    p.add_argument("--pred-eff", type=float, nargs="+", default=PRED_EFF)
    p.add_argument("--pred-upkeep", type=float, nargs="+", default=PRED_UPKEEP)
    p.add_argument("--spec-exp", type=float, nargs="+", default=SPEC_EXP)
    p.add_argument("--out", default="docs/world_study.csv")
    a = p.parse_args()
    grid = ([(*(float(v) for v in g.split(":")), 2.0)[:3] for g in a.grid] if a.grid
            else list(itertools.product(a.pred_eff, a.pred_upkeep, a.spec_exp)))
    jobs = [(pl, sd, pe, pu, se, a.steps) for (pe, pu, se), pl, sd in itertools.product(grid, a.planets, a.seeds)]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, jobs))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
