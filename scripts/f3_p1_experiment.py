"""F3 re-run at the P1 standard: is phototaxis selected?

Arms: off (sensing off: the sensor genes are inert), free (sensing on, sense_upkeep 0), on (sensing on, default
sense_upkeep), control (sensing on, sense_upkeep 0.5: the positive control). P1 standard: 30k steps, second half,
sampled every 10 steps, descendants only, immigration 0, two day/night planets x seeds 1 3 ... 19 = 20 pairs.

Verdict rules (fixed in PLAN.md before running):
1. positive control: mean |w_light| control < free in >= 16/20, else the assay is blind;
2. phototaxis: mean w_light (all descendants) free > off in >= 16/20 -> towards light, < in >= 16/20 -> away;
3. secondary: the same on motile unbonded descendants, pairs with >= 10 of them per sample in both arms only;
4. exploratory: the other weights free vs off, w_light on vs off;
5. exploratory: population, species, motile share free vs off;
6. exactly 16/20 is "at the threshold, not confirmed on new seeds".

    python scripts/f3_p1_experiment.py --steps 30000
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
from worldsim.world import G_W_LIGHT  # noqa: E402
from worldsim.worldgen import load_planet  # noqa: E402

SAMPLE_EVERY = 10
PLANETS = ["flat_seasons", "examples/volcanic.json"]
WEIGHTS = ["w_light", "w_organic", "w_chem", "w_kin", "w_stranger", "w_danger"]
ARMS = {"off": [], "free": ["sensing=1", "sense_upkeep=0"], "on": ["sensing=1"],
        "control": ["sensing=1", "sense_upkeep=0.5"]}
NEED = 16
MIN_MOTILE = 10


def make_world(planet, seed, arm):
    base = Config().apply_overrides(["immigration_rate=0", *ARMS[arm]])
    if planet == "flat_seasons":
        return World(base.apply_overrides(["day_amplitude=1", "season_amplitude=0.5"]).validate(), seed=seed)
    cfg, terrain, seed = load_planet(planet, base, seed)
    return World(cfg, seed=seed, terrain=terrain)


def run(job):
    planet, seed, arm, steps = job
    w = make_world(planet, seed, arm)
    samples = n_desc = n_motile = 0
    wsum = [0.0] * len(WEIGHTS)
    abs_light = motile_light = 0.0
    window = {"population": [], "species": [], "motile_share": []}
    for t in range(steps):
        w.step()
        if t < steps // 2 or t % SAMPLE_EVERY:
            continue
        samples += 1
        cells = w.cells
        s = w.stats()
        window["population"].append(s["population"])
        window["species"].append(s.get("species") or 0)
        motile_here = 0
        for c in cells:
            if c.id == c.lineage:
                continue
            ws = [2 * g - 1 for g in c.genes[G_W_LIGHT:G_W_LIGHT + 6]]
            n_desc += 1
            for i, v in enumerate(ws):
                wsum[i] += v
            abs_light += abs(ws[0])
            if not c.bonds and c.move > 0.3:
                motile_here += 1
                motile_light += ws[0]
        n_motile += motile_here
        window["motile_share"].append(motile_here / len(cells) if cells else 0.0)
    row = {"planet": Path(planet).stem, "seed": seed, "arm": arm,
           "descendants": round(n_desc / max(1, samples), 1)}
    for name, v in zip(WEIGHTS, wsum):
        row[name] = round(v / n_desc, 4) if n_desc else ""
    row["abs_w_light"] = round(abs_light / n_desc, 4) if n_desc else ""
    row["motile"] = round(n_motile / max(1, samples), 2)
    row["motile_w_light"] = round(motile_light / n_motile, 4) if n_motile else ""
    for k, v in window.items():
        row[k] = round(st.mean(v), 4) if v else ""
    row["extinctions"] = w.extinctions
    return row


def at_threshold(k, need):
    """PLAN rule 6: a count of exactly `need` is not a confirmed verdict."""
    return " (at the threshold, not confirmed on new seeds)" if k == need else ""


def count(rows, a, b, key, sign, keep=lambda ra, rb: True):
    by = {(r["planet"], r["seed"], r["arm"]): r for r in rows}
    pairs = sorted({(r["planet"], r["seed"]) for r in rows})
    vals = []
    for p, s in pairs:
        ra, rb = by.get((p, s, a)), by.get((p, s, b))
        if ra and rb and ra[key] != "" and rb[key] != "" and keep(ra, rb):
            vals.append((ra[key], rb[key]))
    return sum((x > y) if sign > 0 else (x < y) for x, y in vals), len(vals)


def spread(rows, arm, key):
    v = sorted(r[key] for r in rows if r["arm"] == arm and r[key] != "")
    return f"median {st.median(v):.4g} (range {v[0]:.4g}-{v[-1]:.4g})" if v else "-"


def verdict(rows, need=NEED):
    lines = []
    down, n = count(rows, "control", "free", "abs_w_light", -1)
    fired = down >= need
    state = "FIRES" + at_threshold(down, need) if fired else "BLIND"
    lines.append(f"positive control: |w_light| control < free in {down}/{n} -> {state}; "
                 f"control {spread(rows, 'control', 'abs_w_light')}, free {spread(rows, 'free', 'abs_w_light')}")
    up, n = count(rows, "free", "off", "w_light", +1)
    down, _ = count(rows, "free", "off", "w_light", -1)
    v = ("TOWARDS LIGHT" + at_threshold(up, need) if up >= need else "AWAY FROM LIGHT" + at_threshold(down, need)
         if down >= need else "no detectable selection")
    lines.append(f"phototaxis (w_light free vs off): higher in {up}/{n}, lower in {down}/{n} -> "
                 f"{v if fired else 'not claimed (control did not fire)'}; "
                 f"free {spread(rows, 'free', 'w_light')}, off {spread(rows, 'off', 'w_light')}")

    def enough(ra, rb):
        return ra["motile"] >= MIN_MOTILE and rb["motile"] >= MIN_MOTILE
    up, n = count(rows, "free", "off", "motile_w_light", +1, enough)
    down, _ = count(rows, "free", "off", "motile_w_light", -1, enough)
    lines.append(f"secondary, motile descendants (usable pairs {n}): higher in {up}, lower in {down}"
                 f"{'' if n >= need else ' -> too few usable pairs, no verdict'}")
    for key in WEIGHTS[1:]:
        up, n = count(rows, "free", "off", key, +1)
        down, _ = count(rows, "free", "off", key, -1)
        lines.append(f"exploratory {key} free vs off: higher in {up}/{n}, lower in {down}/{n}")
    up, n = count(rows, "on", "off", "w_light", +1)
    down, _ = count(rows, "on", "off", "w_light", -1)
    lines.append(f"exploratory w_light on (default cost) vs off: higher in {up}/{n}, lower in {down}/{n}")
    for key in ("population", "species", "motile_share"):
        up, n = count(rows, "free", "off", key, +1)
        down, _ = count(rows, "free", "off", key, -1)
        lines.append(f"exploratory {key} free vs off: higher in {up}/{n}, lower in {down}/{n}; "
                     f"free {spread(rows, 'free', key)}, off {spread(rows, 'off', key)}")
    return lines


def load_csv(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    for r in rows:
        for k, v in r.items():
            if k not in ("planet", "arm") and v != "":
                r[k] = float(v)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--steps", type=int, default=30000)
    p.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 20, 2)))
    p.add_argument("--planets", nargs="+", default=PLANETS)
    p.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    p.add_argument("--need", type=int, default=NEED, help="pairs that must agree for a verdict")
    p.add_argument("--out", default="docs/f3_p1_experiment.csv")
    p.add_argument("--verdict-only", action="store_true", help="recompute the verdict from --out")
    a = p.parse_args()
    if a.verdict_only:
        print("\n".join(verdict(load_csv(a.out), a.need)))
        return
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
