"""ADR-0014 experiment: is an evolvable perception radius sense_r selected, and does it bring hunting or fleeing?

Arms (all with sensing on, immigration 0): off (radius 1, no sense_r), on (sense_range: sense_r widens the
perception radius, default cost), neutral (sense_r inherited, mutated and paid for, radius stays 1: on vs neutral
isolates what the wider view does), control (neutral with sense_range_upkeep 0.5: the positive control, the cost
must visibly pull sense_r down). P1 standard: 30k steps, second half, descendants only, two day/night planets x
seeds 1 3 ... 19 = 20 pairs. `--defence` repeats it with F5e armour on in every arm (longer lives, ADR-0014: part
of the plan, not a rescue).

Verdict rules (fixed in ADR-0014 and PLAN item 15 before running):
1. positive control: sense_r control < neutral in >= 16/20, else rule 2 is not claimed;
2. selection (the ADR's question 1): sense_r on > neutral in >= 16/20 -> SELECTED, on < neutral in >= 16/20 ->
   SELECTED AGAINST, otherwise no detectable selection;
3. behaviour (question 2), on vs neutral at >= 16/20: fleeing = mean w_danger of descendants lower; hunting = share
   of predation attempts made by mobile, unbonded predators (move > 0.3) higher; on vs off reported too;
4. a count of exactly 16/20 is "at the threshold, not confirmed on new seeds".

    python scripts/sense_range_experiment.py --steps 30000
    python scripts/sense_range_experiment.py --steps 30000 --defence --out docs/sense_range_defence.csv
"""
import argparse
import csv
import itertools
import statistics as st
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from f5e_experiment import count, direction, spread  # noqa: E402

from worldsim import Config, World  # noqa: E402
from worldsim.world import G_W_DANGER, sense_radius  # noqa: E402
from worldsim.worldgen import load_planet  # noqa: E402

SAMPLE_EVERY = 100
MOBILE = 0.3                      # move gene above which a predator counts as mobile (as in the F3 experiments)
PLANETS = ["flat_seasons", "examples/volcanic.json"]
ARMS = {"off": [], "on": ["sense_range=1"],
        "neutral": ["sense_range=1", "sense_range_neutral=1"],
        "control": ["sense_range=1", "sense_range_neutral=1", "sense_range_upkeep=0.5"]}
NEED = 16


class ObservedWorld(World):
    """Counts predation attempts by mobile, unbonded predators. An observer only: it calls the parent's
    `random_prey` unchanged (same RNG draws) and never alters its result."""
    attempts = mobile_attempts = 0

    def random_prey(self, c):
        prey = super().random_prey(c)
        if prey is not None:
            self.attempts += 1
            if not c.bonds and c.move > MOBILE:
                self.mobile_attempts += 1
        return prey


def make_world(planet, seed, arm, defence):
    sets = ["immigration_rate=0", "sensing=1", *ARMS[arm], *(["defence=1"] if defence else [])]
    base = Config().apply_overrides(sets)
    if planet == "flat_seasons":
        return ObservedWorld(base.apply_overrides(["day_amplitude=1", "season_amplitude=0.5"]).validate(),
                             seed=seed, track_species=False)
    cfg, terrain, seed = load_planet(planet, base, seed)
    return ObservedWorld(cfg, seed=seed, terrain=terrain, track_species=False)


def run(job):
    planet, seed, arm, steps, defence = job
    w = make_world(planet, seed, arm, defence)
    rmax = w.cfg.sense_radius_max
    sense, radius, danger, pops = [], [], [], []
    for t in range(steps):
        if t == steps // 2:
            attempts0, mobile0, kills0, deaths0 = w.attempts, w.mobile_attempts, w.kills, w.deaths
        w.step()
        if t < steps // 2 or t % SAMPLE_EVERY or not w.cells:
            continue
        pops.append(len(w.cells))
        desc = [c for c in w.cells if c.id != c.lineage]
        if desc:
            danger.append(st.mean(c.genes[G_W_DANGER] * 2.0 - 1.0 for c in desc))
            if w.cfg.sense_range:
                sense.append(st.mean(c.sense_r for c in desc))
                radius.append(st.mean(sense_radius(c.sense_r, rmax) for c in desc))
    attempts, deaths = w.attempts - attempts0, w.deaths - deaths0
    return {"planet": Path(planet).stem, "seed": seed, "arm": arm,
            "sense_r": round(st.mean(sense), 4) if sense else "",
            "radius": round(st.mean(radius), 3) if radius else "",
            "w_danger": round(st.mean(danger), 4) if danger else "",
            "mobile_share": round((w.mobile_attempts - mobile0) / attempts, 4) if attempts else "",
            "kill_share": round((w.kills - kills0) / deaths, 4) if deaths else "",
            "population": round(st.mean(pops), 1) if pops else 0,
            "extinctions": w.extinctions}


def at(k, need):
    return " (at the threshold, not confirmed on new seeds)" if k == need else ""


def verdict(rows, need=NEED):
    down, n = count(rows, "control", "neutral", "sense_r", -1)
    fired = down >= need
    lines = [f"positive control: sense_r control < neutral in {down}/{n} -> "
             f"{'FIRES' + at(down, need) if fired else 'BLIND'}; control {spread(rows, 'control', 'sense_r')}, "
             f"neutral {spread(rows, 'neutral', 'sense_r')}"]
    up, n = count(rows, "on", "neutral", "sense_r", +1)
    dn, _ = count(rows, "on", "neutral", "sense_r", -1)
    v = direction(up, dn, need, "SELECTED", "SELECTED AGAINST", "no detectable selection")
    lines.append(f"selection (on vs neutral): sense_r higher in {up}/{n}, lower in {dn}/{n} -> "
                 f"{v if fired else 'not claimed (control did not fire)'}; on {spread(rows, 'on', 'sense_r')}, "
                 f"mean radius on {spread(rows, 'on', 'radius')}, neutral {spread(rows, 'neutral', 'radius')}")
    for base in ("neutral", "off"):
        dn, n = count(rows, "on", base, "w_danger", -1)
        up, _ = count(rows, "on", base, "w_danger", +1)
        lines.append(f"fleeing, w_danger on vs {base}: lower in {dn}/{n}, higher in {up}/{n} -> "
                     f"{direction(dn, up, need, 'FLEEING (lower)', 'higher', 'no consistent sign')}; "
                     f"on {spread(rows, 'on', 'w_danger')}, {base} {spread(rows, base, 'w_danger')}")
        up, n = count(rows, "on", base, "mobile_share", +1)
        dn, _ = count(rows, "on", base, "mobile_share", -1)
        lines.append(f"hunting, mobile share of attacks on vs {base}: higher in {up}/{n}, lower in {dn}/{n} -> "
                     f"{direction(up, dn, need, 'HUNTING (higher)', 'lower', 'no consistent sign')}; "
                     f"on {spread(rows, 'on', 'mobile_share')}, {base} {spread(rows, base, 'mobile_share')}")
    for key in ("population", "kill_share"):
        up, n = count(rows, "on", "neutral", key, +1)
        dn, _ = count(rows, "on", "neutral", key, -1)
        lines.append(f"{key} on vs neutral: higher in {up}/{n}, lower in {dn}/{n} -> "
                     f"{direction(up, dn, need, 'higher', 'lower', 'no consistent sign')}")
    lines.append(f"extinctions per arm: { {a: sum(r['extinctions'] for r in rows if r['arm'] == a) for a in ARMS} }")
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--steps", type=int, default=30000)
    p.add_argument("--seeds", type=int, nargs="+", default=list(range(1, 20, 2)))
    p.add_argument("--planets", nargs="+", default=PLANETS)
    p.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    p.add_argument("--defence", action="store_true", help="F5e armour on in every arm (longer lives)")
    p.add_argument("--need", type=int, default=NEED, help="pairs that must agree for a verdict")
    p.add_argument("--out", default="docs/sense_range_experiment.csv")
    a = p.parse_args()
    jobs = [(pl, sd, arm, a.steps, a.defence) for pl, sd, arm in itertools.product(a.planets, a.seeds, a.arms)]
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
