"""F4 experiment: do variable-length rule genes earn their keep, and is any rule type selected?

Arms (all with sensing on, immigration 0.5): F3 (open genome off), rules on, rules neutral (they exist, mutate
and cost the same but do nothing). Planets: flat with a day/night cycle, examples/volcanic.json. Seeds 1 3 5 7 9.
Measured over the second half of the run, every SAMPLE_EVERY steps, on descendants only (seeded cells and
immigrants start with no rules, and would dilute the sample).

Verdict rule (fixed in PLAN.md before running):
- rules earn their keep if the mean rule count with rules on exceeds neutral in >= 8 of 10 planet x seed pairs;
- a behaviour is selected if the same rule type (condition x target x sign of intensity) is among the 3 most
  enriched (share on - share neutral) in >= 6 of 10 pairs.

    python scripts/f4_experiment.py --steps 10000
"""
import argparse
import csv
import itertools
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worldsim import Config, World  # noqa: E402
from worldsim.world import RULE_CONDITIONS, RULE_TARGETS, decode_rule  # noqa: E402
from worldsim.worldgen import load_planet  # noqa: E402

SAMPLE_EVERY = 10
PLANETS = ["flat_day", "examples/volcanic.json"]
ARMS = {"f3": [], "on": ["open_genome=1"], "neutral": ["open_genome=1", "rules_neutral=1"]}
TOP_K, KEEP_PAIRS, TYPE_PAIRS = 3, 8, 6


def make_world(planet, seed, arm, immigration=0.5):
    base = Config().apply_overrides(["sensing=1", f"immigration_rate={immigration}", *ARMS[arm]])
    if planet == "flat_day":
        return World(base.apply_overrides(["day_amplitude=1"]).validate(), seed=seed)
    cfg, terrain, seed = load_planet(planet, base, seed)
    return World(cfg, seed=seed, terrain=terrain)


def rule_type(r):
    cond, _, target, w = decode_rule(r)
    return f"{RULE_CONDITIONS[cond]}|{RULE_TARGETS[target]}|{'+' if w >= 0 else '-'}"


def run(job):
    planet, seed, arm, steps, immigration = job
    w = make_world(planet, seed, arm, immigration)
    t0 = time.perf_counter()
    n_cells = n_rules = n_cond = samples = 0
    types = Counter()
    for t in range(steps):
        w.step()
        if t < steps // 2 or t % SAMPLE_EVERY:
            continue
        samples += 1
        for c in w.cells:
            if c.id == c.lineage:
                continue
            n_cells += 1
            n_rules += len(c.rules)
            for r in c.rules:
                types[rule_type(r)] += 1
                n_cond += r[0] * len(RULE_CONDITIONS) >= 1.0
    s = w.stats()
    row = {"planet": Path(planet).stem, "seed": seed, "arm": arm,
           "steps_per_s": round(steps / (time.perf_counter() - t0)),
           "population": s["population"], "photo": s["photo"], "sapro": s["sapro"], "pred": s["pred"],
           "chemo": s["chemo"], "species": s.get("species"), "novelty": s.get("novelty"),
           "speciations": s.get("speciations"),
           "descendants": round(n_cells / max(1, samples), 1),
           "rules_mean": round(n_rules / max(1, n_cells), 3),
           "conditional_share": round(n_cond / max(1, n_rules), 3),
           "rules_max_final": s["rules_max"]}
    return row, {k: v / max(1, n_rules) for k, v in types.items()}


def verdict(rows, shares):
    """Apply the verdict rule; return printable lines."""
    by = {(r["planet"], r["seed"], r["arm"]): r for r in rows}
    pairs = sorted({(r["planet"], r["seed"]) for r in rows})
    keep = sum(by[(p, s, "on")]["rules_mean"] > by[(p, s, "neutral")]["rules_mean"] for p, s in pairs)
    top = Counter()
    lines = []
    for p, s in pairs:
        on, ne = shares[(p, s, "on")], shares[(p, s, "neutral")]
        enr = sorted(((on.get(k, 0.0) - ne.get(k, 0.0), k) for k in set(on) | set(ne)), reverse=True)[:TOP_K]
        top.update(k for _, k in enr)
        lines.append(f"  {p} seed {s}: rules on {by[(p, s, 'on')]['rules_mean']:.2f} vs neutral "
                     f"{by[(p, s, 'neutral')]['rules_mean']:.2f}; top enriched "
                     + ", ".join(f"{k} {d:+.3f}" for d, k in enr))
    selected = [(k, n) for k, n in top.most_common() if n >= TYPE_PAIRS]
    lines.insert(0, f"rules earn their keep: {keep}/{len(pairs)} pairs (needs >= {KEEP_PAIRS}) -> "
                    f"{'YES' if keep >= KEEP_PAIRS else 'no'}")
    lines.insert(1, f"selected rule types (top {TOP_K} in >= {TYPE_PAIRS} pairs): "
                    + (", ".join(f"{k} ({n})" for k, n in selected) or "none")
                    + f"; most frequent in top {TOP_K}: " + ", ".join(f"{k} ({n})" for k, n in top.most_common(5)))
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--steps", type=int, default=10000)
    p.add_argument("--seeds", type=int, nargs="+", default=[1, 3, 5, 7, 9])
    p.add_argument("--planets", nargs="+", default=PLANETS)
    p.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    p.add_argument("--immigration", type=float, default=0.5)
    p.add_argument("--out", default="docs/f4_experiment.csv")
    a = p.parse_args()
    jobs = [(pl, sd, arm, a.steps, a.immigration) for pl, sd, arm in itertools.product(a.planets, a.seeds, a.arms)]
    with ProcessPoolExecutor() as ex:
        results = list(ex.map(run, jobs))
    rows = [r for r, _ in results]
    shares = {(r["planet"], r["seed"], r["arm"]): sh for r, sh in results}
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    types_out = Path(a.out).with_name(Path(a.out).stem + "_rule_types.csv")
    with open(types_out, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["planet", "seed", "arm", "rule_type", "share"])
        for (pl, sd, arm), sh in sorted(shares.items()):
            for k, v in sorted(sh.items()):
                wr.writerow([pl, sd, arm, k, round(v, 4)])
    for r in rows:
        print(r)
    print("\n".join(verdict(rows, shares)))


if __name__ == "__main__":
    main()
