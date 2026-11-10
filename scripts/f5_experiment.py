"""F5a experiment: is sex (recombination with a partner) selected, and what does it change?

Arms (immigration 0.5): off (asexual), on (evolvable propensity sex_p, sex_cost 0), on_cost (sex_cost 1, a fifth of
body_cost), neutral (sex_p inherited and mutated, mating never happens: its drift baseline). Planets: flat with
day/night and seasons, examples/volcanic.json. Seeds 1 3 5 7 9. Measured over the second half of the run, every
SAMPLE_EVERY steps, on descendants only (seeded cells and immigrants draw sex_p at random).

Verdict rule (fixed in PLAN.md before running):
- sex is selected if mean sex_p (on) > neutral in >= 8 of 10 planet x seed pairs, selected against if lower in
  >= 8 of 10; the same rule for on_cost; any positive verdict needs a confirmatory run on new seeds;
- consequences (on vs off) are claimed only where the sign agrees in >= 8 of 10 pairs; no novelty claim.

    python scripts/f5_experiment.py --steps 10000
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
from worldsim.species import genome_distance  # noqa: E402
from worldsim.worldgen import load_planet  # noqa: E402

SAMPLE_EVERY = 10
PLANETS = ["flat_seasons", "examples/volcanic.json"]
ARMS = {"off": [], "on": ["sex=1"], "on_cost": ["sex=1", "sex_cost=1"],
        "on_cost4": ["sex=1", "sex_cost=4"], "neutral": ["sex=1", "sex_neutral=1"]}
NEED = 8
WINDOW = ("population", "species", "in_colony", "mean_mut", "mean_div")   # averaged over the samples


def make_world(planet, seed, arm):
    base = Config().apply_overrides(["immigration_rate=0.5", *ARMS[arm]])
    if planet == "flat_seasons":
        return World(base.apply_overrides(["day_amplitude=1", "season_amplitude=0.5"]).validate(), seed=seed)
    cfg, terrain, seed = load_planet(planet, base, seed)
    return World(cfg, seed=seed, terrain=terrain)


def run(job):
    planet, seed, arm, steps = job
    w = make_world(planet, seed, arm)
    # Instrument partner search (observation only: it neither draws nor changes anything).
    tries = {"n": 0, "found": 0, "dist": []}
    find = w.find_mate

    def counted(c):
        mate = find(c)
        tries["n"] += 1
        if mate is not None:
            tries["found"] += 1
            tries["dist"].append(genome_distance(c.genes, mate.genes))
        return mate
    w.find_mate = counted
    sex_sum = n_desc = samples = 0
    diversity, window = [], {k: [] for k in WINDOW}
    births0 = sex0 = 0
    for t in range(steps):
        if t == steps // 2:
            births0, sex0 = w.births, w.sex_births
            tries.update(n=0, found=0, dist=[])
        w.step()
        if t < steps // 2 or t % SAMPLE_EVERY:
            continue
        samples += 1
        s = w.stats()
        for k in WINDOW:
            window[k].append(s.get(k) or 0)
        desc = [c for c in w.cells if c.id != c.lineage]
        n_desc += len(desc)
        sex_sum += sum(c.sex_p for c in desc)
        if len(desc) > 1:
            diversity.append(st.mean(st.pstdev(g) for g in zip(*(c.genes for c in desc))))
    s = w.stats()
    births = w.births - births0
    mean = {k: round(st.mean(v), 4) if v else "" for k, v in window.items()}
    return {"planet": Path(planet).stem, "seed": seed, "arm": arm,
            "population": mean["population"], "species": mean["species"], "in_colony": mean["in_colony"],
            "novelty_final": s.get("novelty"), "descendants": round(n_desc / max(1, samples), 1),
            "sex_p": round(sex_sum / max(1, n_desc), 4),
            "sexual_birth_share": round((w.sex_births - sex0) / max(1, births), 4),
            "partner_found_share": round(tries["found"] / tries["n"], 3) if tries["n"] else "",
            "mate_distance_mean": round(st.mean(tries["dist"]), 4) if tries["dist"] else "",
            "diversity": round(st.mean(diversity), 4) if diversity else "",
            "mean_mut": mean["mean_mut"], "mean_div": mean["mean_div"]}


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
    lines = []
    for arm in ("on", "on_cost"):
        up, n = count(rows, arm, "neutral", "sex_p", +1)
        down, _ = count(rows, arm, "neutral", "sex_p", -1)
        v = "SELECTED" if up >= need else "SELECTED AGAINST" if down >= need else "no detectable selection"
        lines.append(f"sex_p {arm} vs neutral: higher in {up}/{n}, lower in {down}/{n} -> {v}; "
                     f"{arm} {spread(rows, arm, 'sex_p')}, neutral {spread(rows, 'neutral', 'sex_p')}")
    for key in ("population", "diversity", "species", "mean_mut", "mean_div", "in_colony"):
        up, n = count(rows, "on", "off", key, +1)
        down, _ = count(rows, "on", "off", key, -1)
        claim = "higher" if up >= need else "lower" if down >= need else "no consistent sign"
        lines.append(f"{key} on vs off: higher in {up}/{n}, lower in {down}/{n} -> {claim}; "
                     f"on {spread(rows, 'on', key)}, off {spread(rows, 'off', key)}")
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--steps", type=int, default=10000)
    p.add_argument("--seeds", type=int, nargs="+", default=[1, 3, 5, 7, 9])
    p.add_argument("--planets", nargs="+", default=PLANETS)
    p.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    p.add_argument("--need", type=int, default=NEED, help="pairs that must agree for a verdict")
    p.add_argument("--out", default="docs/f5_experiment.csv")
    a = p.parse_args()
    jobs = [(pl, sd, arm, a.steps) for pl, sd, arm in itertools.product(a.planets, a.seeds, a.arms)]
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
