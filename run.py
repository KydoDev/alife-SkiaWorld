"""Headless run: simulate N steps, save CSV statistics, PNG snapshots and a plot.

Example:
    python run.py --steps 5000 --seed 1 --out runs/test1
"""
import argparse
import csv
import json
import os
import time

from worldsim import Config, World
from worldsim.render import save_png


def plot_stats(csv_path, png_path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: plot skipped")
        return
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    if not rows:
        return
    step = [int(r["step"]) for r in rows]
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    ax = axes[0]
    ax.plot(step, [int(r["photo"]) for r in rows], color="#3cb446", label="photosynthesis")
    ax.plot(step, [int(r["sapro"]) for r in rows], color="#9a5ae6", label="decomposers")
    ax.plot(step, [int(r["pred"]) for r in rows], color="#e0322d", label="predators")
    ax.set_ylabel("cells")
    ax.legend(loc="upper left")
    ax.set_title("Population by dominant strategy")
    ax = axes[1]
    for g in ["move", "attach", "share", "mut", "div"]:
        ax.plot(step, [float(r["mean_" + g]) for r in rows], label=g)
    ax.set_ylabel("mean gene value")
    ax.legend(loc="upper left", ncol=5)
    ax = axes[2]
    pop = [max(int(r["population"]), 1) for r in rows]
    ax.plot(step, [int(r["in_colony"]) / p for r, p in zip(rows, pop)], label="% in colony")
    ax.plot(step, [int(r["lineages"]) / 400 for r in rows], label="lineages / 400")
    ax.set_ylabel("fraction")
    ax.set_xlabel("step")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(png_path, dpi=110)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description="WorldSim v0 headless")
    p.add_argument("--steps", type=int, default=3000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", default="runs/default")
    p.add_argument("--stats-every", type=int, default=10)
    p.add_argument("--snap-every", type=int, default=500)
    p.add_argument("--width", type=int, default=None)
    p.add_argument("--height", type=int, default=None)
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override a Config parameter, e.g. --set photo_gain=2")
    args = p.parse_args()

    cfg = Config()
    if args.width:
        cfg.width = args.width
    if args.height:
        cfg.height = args.height
    for kv in args.set:
        k, v = kv.split("=", 1)
        if not hasattr(cfg, k):
            raise SystemExit(f"Unknown parameter: {k}")
        cur = getattr(cfg, k)
        setattr(cfg, k, type(cur)(v) if not isinstance(cur, bool) else v.lower() in ("1", "true", "si", "yes"))
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"seed": args.seed, **cfg.to_dict()}, f, indent=2)

    world = World(cfg, seed=args.seed)
    csv_path = os.path.join(args.out, "stats.csv")
    writer = None
    t0 = time.time()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        for _ in range(args.steps):
            world.step()
            st = world.step_count
            if st % args.stats_every == 0:
                s = world.stats()
                if writer is None:
                    writer = csv.DictWriter(f, fieldnames=list(s.keys()))
                    writer.writeheader()
                writer.writerow(s)
            if st % args.snap_every == 0:
                save_png(world, os.path.join(args.out, f"snap_{st:06d}.png"))
                s = world.stats()
                print(f"[{st:6d}] pop={s['population']:5d} photo={s['photo']:5d} "
                      f"sapro={s['sapro']:5d} pred={s['pred']:5d} colony={s['in_colony']:5d} "
                      f"lineages={s['lineages']:3d} extinctions={s['extinctions']} "
                      f"({time.time() - t0:.0f}s)", flush=True)
    plot_stats(csv_path, os.path.join(args.out, "stats.png"))
    print("Done:", args.out)


if __name__ == "__main__":
    main()
