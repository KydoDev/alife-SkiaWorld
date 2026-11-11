"""F5e experiment: does prey armour make a long-life world, and is armour selected?

Arms: off (every attack succeeds), on (evolvable armour armor_p, default strength and upkeep), neutral (armor_p
inherited and mutated, no effect, no cost: the drift baseline), neutral_cost (neutral with the default
defence_upkeep: on vs neutral_cost isolates the effect of armour), control (neutral with defence_upkeep 1.0: the
positive control). P1 standard: 30k steps, second half, descendants only, immigration 0, two day/night planets
x seeds 1 3 ... 19 = 20 pairs.

Verdict rules (fixed in PLAN.md before running):
1. primary, the world: `on` is the long-life world if, in >= 16/20 pairs, median age at death of descendants >= 20,
   mean population >= 300, no extinction and predators present (mean share > 0) in the last third;
2. positive control: armor_p control < neutral in >= 16/20, else rules 3-4 are not claimed;
3. on vs neutral_cost: armor_p higher in >= 16/20 -> beneficial, lower -> harmful;
4. on vs neutral: net selection, same thresholds;
5. consequences on vs neutral_cost (median life, kills / deaths, population, predator share) at >= 16/20;
   on vs off reported too;
6. a count of exactly 16/20 is "at the threshold, not confirmed on new seeds".

    python scripts/f5e_experiment.py --steps 30000
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

SAMPLE_EVERY = 100
PLANETS = ["flat_seasons", "examples/volcanic.json"]
ARMS = {"off": [], "on": ["defence=1"],
        "neutral": ["defence=1", "defence_neutral=1", "defence_upkeep=0"],
        "neutral_cost": ["defence=1", "defence_neutral=1"],
        "control": ["defence=1", "defence_neutral=1", "defence_upkeep=1.0"]}
NEED = 16
MIN_LIFE, MIN_POP = 20, 300


def make_world(planet, seed, arm):
    base = Config().apply_overrides(["immigration_rate=0", *ARMS[arm]])
    if planet == "flat_seasons":
        return World(base.apply_overrides(["day_amplitude=1", "season_amplitude=0.5"]).validate(), seed=seed)
    cfg, terrain, seed = load_planet(planet, base, seed)
    return World(cfg, seed=seed, terrain=terrain)


def run(job):
    planet, seed, arm, steps = job
    w = make_world(planet, seed, arm)
    ages, pops, preds_late, armour = [], [], [], []
    deaths0 = kills0 = defended0 = 0
    for t in range(steps):
        if t == steps // 2:
            deaths0, kills0, defended0 = w.deaths, w.kills, w.defended
        before = {c.id: c for c in w.cells} if t >= steps // 2 else None
        w.step()
        if before is None:
            continue
        alive = {c.id for c in w.cells}
        ages += [c.age for i, c in before.items() if i not in alive and c.id != c.lineage]
        if t % SAMPLE_EVERY or not w.cells:
            continue
        n = len(w.cells)
        pops.append(n)
        desc = [c.armor_p for c in w.cells if c.id != c.lineage]
        if desc:
            armour.append(st.mean(desc))
        if t >= 2 * steps // 3:
            preds_late.append(sum(c.strategy == "pred" for c in w.cells) / n)
    deaths, kills = w.deaths - deaths0, w.kills - kills0
    attacks = kills + w.defended - defended0
    return {"planet": Path(planet).stem, "seed": seed, "arm": arm,
            "median_life": st.median(ages) if ages else 0,
            "population": round(st.mean(pops), 1) if pops else 0,
            "pred_late": round(st.mean(preds_late), 4) if preds_late else 0,
            "kill_share": round(kills / deaths, 4) if deaths else "",
            "repelled_share": round((w.defended - defended0) / attacks, 4) if attacks else "",
            "armor_p": round(st.mean(armour), 4) if armour else "",
            "extinctions": w.extinctions}


def long_life(r):
    return (r["median_life"] >= MIN_LIFE and r["population"] >= MIN_POP and r["extinctions"] == 0
            and r["pred_late"] > 0)


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
    """PLAN rule 6: a count of exactly `need` is not a confirmed verdict."""
    return " (at the threshold, not confirmed on new seeds)" if k == need else ""


def direction(up, down, need, hi, lo, none):
    if up >= need:
        return hi + at_threshold(up, need)
    if down >= need:
        return lo + at_threshold(down, need)
    return none


def verdict(rows, need=NEED):
    lines = []
    on = [r for r in rows if r["arm"] == "on"]
    ok = sum(long_life(r) for r in on)
    fails = {k: sum(not f(r) for r in on) for k, f in (
        ("median_life", lambda r: r["median_life"] >= MIN_LIFE), ("population", lambda r: r["population"] >= MIN_POP),
        ("extinction", lambda r: r["extinctions"] == 0), ("predators", lambda r: r["pred_late"] > 0))}
    state = "LONG-LIFE WORLD" + at_threshold(ok, need) if ok >= need else "NOT a long-life world"
    lines.append(f"primary: on passes all four criteria in {ok}/{len(on)} -> {state}; failures per criterion {fails}")
    for key in ("median_life", "population", "pred_late", "kill_share"):
        lines.append(f"  {key}: on {spread(rows, 'on', key)}; off {spread(rows, 'off', key)}")
    down, n = count(rows, "control", "neutral", "armor_p", -1)
    fired = down >= need
    lines.append(f"positive control: armor_p control < neutral in {down}/{n} -> "
                 f"{'FIRES' + at_threshold(down, need) if fired else 'BLIND'}; "
                 f"control {spread(rows, 'control', 'armor_p')}, neutral {spread(rows, 'neutral', 'armor_p')}")
    for b, label, hi, lo in (("neutral_cost", "armour, cost-matched (on vs neutral_cost)", "BENEFICIAL", "HARMFUL"),
                             ("neutral", "net selection (on vs neutral)", "SELECTED", "SELECTED AGAINST")):
        up, n = count(rows, "on", b, "armor_p", +1)
        dn, _ = count(rows, "on", b, "armor_p", -1)
        v = direction(up, dn, need, hi, lo, "no detectable effect")
        lines.append(f"{label}: higher in {up}/{n}, lower in {dn}/{n} -> "
                     f"{v if fired else 'not claimed (control did not fire)'}; on {spread(rows, 'on', 'armor_p')}, "
                     f"{b} {spread(rows, b, 'armor_p')}")
    lines.append(f"mechanism: repelled share of attacks, on {spread(rows, 'on', 'repelled_share')}")
    for base in ("neutral_cost", "off"):
        for key in ("median_life", "kill_share", "population", "pred_late"):
            up, n = count(rows, "on", base, key, +1)
            dn, _ = count(rows, "on", base, key, -1)
            v = direction(up, dn, need, "higher", "lower", "no consistent sign")
            lines.append(f"{key} on vs {base}: higher in {up}/{n}, lower in {dn}/{n} -> {v}")
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--steps", type=int, default=30000)
    p.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 20, 2)))
    p.add_argument("--planets", nargs="+", default=PLANETS)
    p.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    p.add_argument("--need", type=int, default=NEED, help="pairs that must agree for a verdict")
    p.add_argument("--out", default="docs/f5e_experiment.csv")
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
