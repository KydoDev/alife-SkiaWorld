"""F5b experiment: is within-life diet plasticity selected, and does it actually move the diet?

Arms: off (fixed diet), on (evolvable acclimation rate plast_p, default plastic_upkeep), neutral (plast_p inherited
and mutated, diet never moves, no cost: the drift baseline), control (neutral with plastic_upkeep 0.2: the positive
control, a pure cost that must lower plast_p), neutral_cost (neutral with the default plastic_upkeep: pays what
`on` pays, so on vs neutral_cost isolates the effect of acclimation). P1 standard: 30k steps, second half,
descendants only, immigration 0, two day/night planets x seeds 1 3 ... 19 = 20 pairs.
Contrast: flat world with constant light (arms on, neutral).

Verdict rules (fixed in PLAN.md before running):
1. positive control: plast_p control < neutral in >= 16/20 pairs, else the assay is blind and nothing is claimed;
2. plast_p on vs neutral: selected if higher in >= 16/20, selected against if lower in >= 16/20;
3. diet shift of descendants in `on` is reported (mechanism check);
4. contrast (exploratory): fewer pairs with on > neutral on the constant-light planet than on the day/night ones;
5. consequences on vs off only at >= 16/20;
6. on vs neutral_cost (cost-matched): acclimation beneficial / harmful at >= 16/20;
7. neutral_cost < neutral in >= 16/20: the assay detects a cost of the size plasticity pays.

    python scripts/f5b_experiment.py --steps 30000
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

SAMPLE_EVERY = 10
PLANETS = ["flat_seasons", "examples/volcanic.json"]
CONTRAST = "flat_constant"
ARMS = {"off": [], "on": ["plasticity=1"],
        "neutral": ["plasticity=1", "plastic_neutral=1", "plastic_upkeep=0"],
        "neutral_cost": ["plasticity=1", "plastic_neutral=1"],
        "control": ["plasticity=1", "plastic_neutral=1", "plastic_upkeep=0.2"]}
CONTRAST_ARMS = ["on", "neutral"]
NEED = 16
WINDOW = ("population", "species", "in_colony")


def make_world(planet, seed, arm, immigration):
    base = Config().apply_overrides([f"immigration_rate={immigration}", *ARMS[arm]])
    if planet == "flat_constant":
        return World(base.validate(), seed=seed)
    if planet == "flat_seasons":
        return World(base.apply_overrides(["day_amplitude=1", "season_amplitude=0.5"]).validate(), seed=seed)
    cfg, terrain, seed = load_planet(planet, base, seed)
    return World(cfg, seed=seed, terrain=terrain)


def run(job):
    planet, seed, arm, steps, immigration = job
    w = make_world(planet, seed, arm, immigration)
    plast_sum = shift_sum = n_desc = samples = 0
    diversity, window = [], {k: [] for k in WINDOW}
    for t in range(steps):
        w.step()
        if t < steps // 2 or t % SAMPLE_EVERY:
            continue
        samples += 1
        s = w.stats()
        for k in WINDOW:
            window[k].append(s.get(k) or 0)
        desc = [c for c in w.cells if c.id != c.lineage]
        n_desc += len(desc)
        plast_sum += sum(c.plast_p for c in desc)
        shift_sum += sum(World.diet_shift(c) for c in desc)
        if len(desc) > 1:
            diversity.append(st.mean(st.pstdev(g) for g in zip(*(c.genes for c in desc))))
    mean = {k: round(st.mean(v), 4) if v else "" for k, v in window.items()}
    return {"planet": Path(planet).stem, "seed": seed, "arm": arm,
            "population": mean["population"], "species": mean["species"], "in_colony": mean["in_colony"],
            "descendants": round(n_desc / max(1, samples), 1),
            "plast_p": round(plast_sum / n_desc, 4) if n_desc else "",
            "diet_shift": round(float(shift_sum) / n_desc, 4) if n_desc else "",
            "diversity": round(st.mean(diversity), 4) if diversity else "",
            "extinctions": w.extinctions}


def count(rows, a, b, key, sign):
    by = {(r["planet"], r["seed"], r["arm"]): r for r in rows}
    pairs = sorted({(r["planet"], r["seed"]) for r in rows})
    vals = [(by[(p, s, a)][key], by[(p, s, b)][key]) for p, s in pairs
            if (p, s, a) in by and (p, s, b) in by and by[(p, s, a)][key] != "" and by[(p, s, b)][key] != ""]
    return sum((x > y) if sign > 0 else (x < y) for x, y in vals), len(vals)


def spread(rows, arm, key):
    v = sorted(r[key] for r in rows if r["arm"] == arm and r[key] != "")
    return f"median {st.median(v):.4g} (range {v[0]:.4g}-{v[-1]:.4g})" if v else "-"


def verdict(rows, need=NEED):
    main = [r for r in rows if r["planet"] != CONTRAST]
    contrast = [r for r in rows if r["planet"] == CONTRAST]
    lines = []
    down, n = count(main, "control", "neutral", "plast_p", -1)
    fired = down >= need
    lines.append(f"positive control: plast_p control < neutral in {down}/{n} -> {'FIRES' if fired else 'BLIND'}; "
                 f"control {spread(main, 'control', 'plast_p')}, neutral {spread(main, 'neutral', 'plast_p')}")
    up, n = count(main, "on", "neutral", "plast_p", +1)
    down, _ = count(main, "on", "neutral", "plast_p", -1)
    v = ("SELECTED" if up >= need else "SELECTED AGAINST" if down >= need else "no detectable selection")
    lines.append(f"plast_p on vs neutral: higher in {up}/{n}, lower in {down}/{n} -> "
                 f"{v if fired else 'not claimed (control did not fire)'}; on {spread(main, 'on', 'plast_p')}")
    up6, n6 = count(main, "on", "neutral_cost", "plast_p", +1)
    down6, _ = count(main, "on", "neutral_cost", "plast_p", -1)
    v6 = "BENEFICIAL" if up6 >= need else "HARMFUL" if down6 >= need else "no detectable effect"
    lines.append(f"acclimation, cost-matched (on vs neutral_cost): higher in {up6}/{n6}, lower in {down6}/{n6} "
                 f"-> {v6}; neutral_cost {spread(main, 'neutral_cost', 'plast_p')}")
    low7, n7 = count(main, "neutral_cost", "neutral", "plast_p", -1)
    lines.append(f"power at the real cost: neutral_cost < neutral in {low7}/{n7} -> "
                 f"{'detected' if low7 >= need else 'not detected'}")
    lines.append(f"diet shift (on, descendants): {spread(main, 'on', 'diet_shift')}; "
                 f"neutral {spread(main, 'neutral', 'diet_shift')}")
    if contrast:
        cu, cn = count(contrast, "on", "neutral", "plast_p", +1)
        lines.append(f"contrast (constant light): on > neutral in {cu}/{cn} vs {up}/{n} on day/night planets; "
                     f"diet shift {spread(contrast, 'on', 'diet_shift')}")
    for key in ("population", "diversity", "species", "in_colony"):
        up, n = count(main, "on", "off", key, +1)
        down, _ = count(main, "on", "off", key, -1)
        claim = "higher" if up >= need else "lower" if down >= need else "no consistent sign"
        lines.append(f"{key} on vs off: higher in {up}/{n}, lower in {down}/{n} -> {claim}; "
                     f"on {spread(main, 'on', key)}, off {spread(main, 'off', key)}")
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--steps", type=int, default=30000)
    p.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 20, 2)))
    p.add_argument("--planets", nargs="+", default=PLANETS)
    p.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    p.add_argument("--no-contrast", action="store_true")
    p.add_argument("--need", type=int, default=NEED, help="pairs that must agree for a verdict")
    p.add_argument("--immigration", type=float, default=0.0)
    p.add_argument("--out", default="docs/f5b_experiment.csv")
    a = p.parse_args()
    jobs = [(pl, sd, arm, a.steps, a.immigration) for pl, sd, arm in itertools.product(a.planets, a.seeds, a.arms)]
    if not a.no_contrast:
        jobs += [(CONTRAST, sd, arm, a.steps, a.immigration) for sd, arm in itertools.product(a.seeds, CONTRAST_ARMS)]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, jobs))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    for r in rows:
        print(r)
    print("\n".join(verdict(rows, a.need)))


if __name__ == "__main__":
    main()
