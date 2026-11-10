"""F5c experiment: is horizontal gene transfer selected, and does it do anything here?

Arms: off (genes change only at division), on (evolvable propensity hgt_p, default hgt_upkeep), neutral (hgt_p
inherited and mutated, no transfer, no cost: the drift baseline), neutral_cost (neutral with the default
hgt_upkeep: on vs neutral_cost isolates the effect of transfer), control (neutral with hgt_upkeep 0.2: the
positive control). P1 standard: 30k steps, second half, descendants only, immigration 0, two day/night planets
x seeds 1 3 ... 19 = 20 pairs.
Contrast: flat day/night world with immigration 0.5 (divergent donors; arms on, neutral_cost).

Verdict rules (fixed in PLAN.md before running):
1. positive control: hgt_p control < neutral in >= 16/20 pairs, else the assay is blind and nothing is claimed;
2. on vs neutral_cost (cost-matched): transfer beneficial / harmful at >= 16/20;
3. on vs neutral: selected / selected against at >= 16/20;
4. mechanism (reported): transfers per birth, foreign-donor share, sampled |gene difference| to a neighbour;
5. consequences on vs off only at >= 16/20;
6. neutral_cost < neutral in >= 16/20: the assay detects the default cost;
7. contrast (exploratory): on < neutral_cost in more pairs than in the main runs.
A null with near-clone donors reads "mechanism nearly inert here", not "transfer is not selected".

    python scripts/f5c_experiment.py --steps 30000
"""
import argparse
import csv
import itertools
import random
import statistics as st
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worldsim import Config, World  # noqa: E402
from worldsim.world import N_GENES  # noqa: E402
from worldsim.worldgen import load_planet  # noqa: E402

SAMPLE_EVERY = 10
DELTA_EVERY = 100
N_SAMPLE = 100
PLANETS = ["flat_seasons", "examples/volcanic.json"]
CONTRAST = "flat_immigrants"
CONTRAST_IMMIGRATION = 0.5
ARMS = {"off": [], "on": ["hgt=1"],
        "neutral": ["hgt=1", "hgt_neutral=1", "hgt_upkeep=0"],
        "neutral_cost": ["hgt=1", "hgt_neutral=1"],
        "control": ["hgt=1", "hgt_neutral=1", "hgt_upkeep=0.2"]}
CONTRAST_ARMS = ["on", "neutral_cost"]
NEED = 16
WINDOW = ("population", "species", "in_colony")


def make_world(planet, seed, arm, immigration):
    if planet == CONTRAST:
        immigration = CONTRAST_IMMIGRATION
    base = Config().apply_overrides([f"immigration_rate={immigration}", *ARMS[arm]])
    if planet in ("flat_seasons", CONTRAST):
        return World(base.apply_overrides(["day_amplitude=1", "season_amplitude=0.5"]).validate(), seed=seed)
    cfg, terrain, seed = load_planet(planet, base, seed)
    return World(cfg, seed=seed, terrain=terrain)


def neighbour_difference(w, rnd):
    """|gene difference| between a descendant and a random neighbour at a random fixed locus (sampled)."""
    desc = [c for c in w.cells if c.id != c.lineage]
    out = []
    for c in rnd.sample(desc, min(N_SAMPLE, len(desc))):
        nbs = [o for nx, ny in w.neighbors(c.x, c.y) if (o := w.grid[ny * w.W + nx]) is not None]
        if nbs:
            o, k = rnd.choice(nbs), rnd.randrange(N_GENES)
            out.append(abs(c.genes[k] - o.genes[k]))
    return out


def run(job):
    planet, seed, arm, steps, immigration = job
    w = make_world(planet, seed, arm, immigration)
    rnd = random.Random(seed)                         # the script's own sampler, never the world's RNG
    hgt_sum = n_desc = samples = 0
    diversity, deltas, window = [], [], {k: [] for k in WINDOW}
    half = (0, 0, 0)
    for t in range(steps):
        w.step()
        if t == steps // 2:
            half = (w.hgt_events, w.hgt_foreign, w.births)
        if t < steps // 2 or t % SAMPLE_EVERY:
            continue
        samples += 1
        s = w.stats()
        for k in WINDOW:
            window[k].append(s.get(k) or 0)
        desc = [c for c in w.cells if c.id != c.lineage]
        n_desc += len(desc)
        hgt_sum += sum(c.hgt_p for c in desc)
        if t % DELTA_EVERY == 0:
            deltas += neighbour_difference(w, rnd)
        if len(desc) > 1:
            diversity.append(st.mean(st.pstdev(g) for g in zip(*(c.genes for c in desc))))
    events, foreign, births = w.hgt_events - half[0], w.hgt_foreign - half[1], w.births - half[2]
    mean = {k: round(st.mean(v), 4) if v else "" for k, v in window.items()}
    return {"planet": Path(planet).stem, "seed": seed, "arm": arm,
            "population": mean["population"], "species": mean["species"], "in_colony": mean["in_colony"],
            "descendants": round(n_desc / max(1, samples), 1),
            "hgt_p": round(hgt_sum / n_desc, 4) if n_desc else "",
            "transfers_per_birth": round(events / births, 4) if births else "",
            "foreign_share": round(foreign / events, 4) if events else "",
            "neighbour_delta": round(st.mean(deltas), 4) if deltas else "",
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


def at_threshold(k, need):
    """PLAN rule 8: a count of exactly `need` is not a confirmed verdict."""
    return " (at the threshold, not confirmed on new seeds)" if k == need else ""


def verdict(rows, need=NEED):
    main = [r for r in rows if r["planet"] != CONTRAST]
    contrast = [r for r in rows if r["planet"] == CONTRAST]
    lines = []
    down, n = count(main, "control", "neutral", "hgt_p", -1)
    fired = down >= need
    state = "FIRES" + at_threshold(down, need) if fired else "BLIND"
    lines.append(f"positive control: hgt_p control < neutral in {down}/{n} -> {state}; "
                 f"control {spread(main, 'control', 'hgt_p')}, neutral {spread(main, 'neutral', 'hgt_p')}")
    up2, n2 = count(main, "on", "neutral_cost", "hgt_p", +1)
    down2, _ = count(main, "on", "neutral_cost", "hgt_p", -1)
    v2 = ("BENEFICIAL" + at_threshold(up2, need) if up2 >= need else "HARMFUL" + at_threshold(down2, need)
          if down2 >= need else "no detectable effect")
    lines.append(f"transfer, cost-matched (on vs neutral_cost): higher in {up2}/{n2}, lower in {down2}/{n2} -> "
                 f"{v2 if fired else 'not claimed (control did not fire)'}; "
                 f"on {spread(main, 'on', 'hgt_p')}, neutral_cost {spread(main, 'neutral_cost', 'hgt_p')}")
    up, n = count(main, "on", "neutral", "hgt_p", +1)
    down, _ = count(main, "on", "neutral", "hgt_p", -1)
    v = ("SELECTED" + at_threshold(up, need) if up >= need else "SELECTED AGAINST" + at_threshold(down, need)
         if down >= need else "no detectable selection")
    lines.append(f"net selection (on vs neutral): higher in {up}/{n}, lower in {down}/{n} -> "
                 f"{v if fired else 'not claimed (control did not fire)'}")
    low6, n6 = count(main, "neutral_cost", "neutral", "hgt_p", -1)
    lines.append(f"power at the real cost: neutral_cost < neutral in {low6}/{n6} -> "
                 f"{'detected' + at_threshold(low6, need) if low6 >= need else 'not detected'}")
    for key in ("transfers_per_birth", "foreign_share", "neighbour_delta"):
        lines.append(f"mechanism {key}: on {spread(main, 'on', key)}; neutral {spread(main, 'neutral', key)}")
    if contrast:
        cd, cn = count(contrast, "on", "neutral_cost", "hgt_p", -1)
        lines.append(f"contrast (immigration {CONTRAST_IMMIGRATION}): on < neutral_cost in {cd}/{cn} vs "
                     f"{down2}/{n2} in the main runs; foreign {spread(contrast, 'on', 'foreign_share')}, "
                     f"delta {spread(contrast, 'on', 'neighbour_delta')}")
    for key in ("population", "diversity", "species", "in_colony"):
        up, n = count(main, "on", "off", key, +1)
        down, _ = count(main, "on", "off", key, -1)
        claim = (("higher" + at_threshold(up, need)) if up >= need else ("lower" + at_threshold(down, need))
                 if down >= need else "no consistent sign")
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
    p.add_argument("--out", default="docs/f5c_experiment.csv")
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
