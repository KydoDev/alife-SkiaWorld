"""F3 experiment: does directed movement (sensing) select for behaviour?

Arms: sensing on/off x planet (flat default, examples/volcanic.json) x seed x immigration on/off.
Per run, over the last half of the steps:
- selection signature: mean sensor weights (2g - 1) of motile *descendants* (founders, i.e. seeded cells and
  immigrants, excluded: a light-seeking immigrant lives longer without any inheritance); arms with fewer than
  MIN_MOTILE motile descendants on average are flagged as too small;
- vertical migration: correlation between the light factor and the mean depth of motile photosynthesizers
  (negative = they rise when it is light; needs a day/night planet);
- fleeing / hunting: predation kills per prey-step and per predator-step.

Usage: python scripts/f3_experiment.py --steps 10000 --out docs/f3_experiment.csv
"""
import argparse
import csv
import itertools
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worldsim.config import Config  # noqa: E402
from worldsim.world import G_W_LIGHT, World  # noqa: E402
from worldsim.worldgen import load_planet  # noqa: E402

WEIGHTS = ["w_light", "w_organic", "w_chem", "w_kin", "w_stranger", "w_danger"]
MIN_MOTILE = 10


def make_world(planet, seed, sensing, immigration):
    base = Config().apply_overrides([f"sensing={int(sensing)}", f"immigration_rate={immigration}"])
    if planet == "flat":
        return World(base.validate(), seed=seed)
    cfg, terrain, seed = load_planet(planet, base, seed)
    return World(cfg, seed=seed, terrain=terrain)


def run(arm):
    planet, seed, sensing, immigration, steps = arm
    w = make_world(planet, seed, sensing, immigration)
    depth, factor, kills, prey_steps, pred_steps = [], [], 0, 0, 0
    wsum, wn, lineages = np.zeros(len(WEIGHTS)), 0, set()
    for t in range(steps):
        k0 = w.kills
        w.step()
        if t < steps // 2:
            continue
        kills += w.kills - k0
        photo_y = []
        for c in w.cells:
            if c.strategy == "pred":
                pred_steps += 1
            else:
                prey_steps += 1
            if not c.bonds and c.move > 0.3 and c.id != c.lineage:
                lineages.add(c.lineage)
                wsum += [2 * g - 1 for g in c.genes[G_W_LIGHT:G_W_LIGHT + 6]]
                wn += 1
                if c.strategy == "photo":
                    photo_y.append(c.y)
        if photo_y:
            depth.append(sum(photo_y) / len(photo_y))
            factor.append(w.light_factor(w.step_count))
    corr = (float(np.corrcoef(factor, depth)[0, 1])
            if len(depth) > 2 and np.std(factor) > 0 and np.std(depth) > 0 else float("nan"))
    s = w.stats()
    row = {"planet": Path(planet).stem, "seed": seed, "sensing": int(sensing), "immigration": immigration,
           "population": s["population"], "photo": s["photo"], "sapro": s["sapro"], "pred": s["pred"],
           "chemo": s["chemo"], "species": s.get("species"), "novelty": s.get("novelty"),
           "speciations": s.get("speciations"), "motile_cells": round(wn / max(1, steps - steps // 2), 1),
           "motile_lineages": len(lineages), "enough_sample": int(wn / max(1, steps - steps // 2) >= MIN_MOTILE),
           "light_depth_corr": round(corr, 3),
           "kills_per_prey_step": round(kills / max(1, prey_steps), 6),
           "kills_per_pred_step": round(kills / max(1, pred_steps), 5)}
    row.update({n: round(float(v) / max(1, wn), 3) for n, v in zip(WEIGHTS, wsum)})
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--steps", type=int, default=10000)
    p.add_argument("--seeds", type=int, nargs="+", default=[1, 7])
    p.add_argument("--out", default="docs/f3_experiment.csv")
    a = p.parse_args()
    arms = [(pl, sd, se, im, a.steps) for pl, sd, se, im in
            itertools.product(["flat", "examples/volcanic.json"], a.seeds, [False, True], [0.5, 0.0])]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, arms))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
