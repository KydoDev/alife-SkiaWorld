"""Headless run: simulate N steps and write statistics, snapshots, saves and charts.

Examples:
    python run.py --steps 5000 --seed 1 --out runs/test1
    python run.py --steps 5000 --seed 1 --out runs/test1 --save-every 1000
    python run.py --resume runs/test1/world_003000.json.gz --steps 2000 --out runs/test1b
    python run.py --planet examples/volcanic.json --steps 5000 --out runs/volcanic
    python run.py --planet photo.jpg --steps 5000 --out runs/photo

Outputs in --out: config.json, stats.csv, snap_NNNNNN.png, world_final.json.gz
(plus world_NNNNNN.json.gz with --save-every), stats.png, and with species
tracking: species.csv, species_tree.png, novelty.png.
"""
import argparse
import csv
import json
import os
import time

from plots import plot_novelty, plot_species_tree, plot_stats, write_species_csv
from worldsim import Config, World
from worldsim.persistence import load_world, save_world
from worldsim.render import save_png
from worldsim.worldgen import PlanetError, load_planet


def build_config(args):
    cfg = Config()
    if args.width:
        cfg.width = args.width
    if args.height:
        cfg.height = args.height
    try:
        return cfg.apply_overrides(args.set).validate()
    except ValueError as e:
        raise SystemExit(f"Invalid --set: {e}") from e


def main():
    p = argparse.ArgumentParser(description="WorldSim headless runner")
    p.add_argument("--steps", type=int, default=3000, help="steps to simulate (after the resume point, if any)")
    p.add_argument("--seed", type=int, default=None, help="RNG seed for a new world (default 1)")
    p.add_argument("--out", default="runs/default")
    p.add_argument("--stats-every", type=int, default=10)
    p.add_argument("--snap-every", type=int, default=500)
    p.add_argument("--save-every", type=int, default=0, help="also save the world every N steps (0 = final only)")
    p.add_argument("--resume", metavar="SAVE", help="continue from a world_*.json.gz save file")
    p.add_argument("--no-species", action="store_true", help="disable species tracking")
    p.add_argument("--planet", metavar="FILE",
                   help="generate the world from a planet form (.json) or an image; form fields override --set")
    p.add_argument("--width", type=int, default=None)
    p.add_argument("--height", type=int, default=None)
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override a Config parameter, e.g. --set photo_gain=2")
    args = p.parse_args()

    if args.resume:
        if args.seed is not None or args.set or args.width or args.height or args.no_species or args.planet:
            raise SystemExit("--resume continues the saved world as-is: "
                             "--seed/--set/--width/--height/--no-species/--planet are not allowed")
        world = load_world(args.resume)
        meta = {"resumed_from": args.resume, "resumed_at_step": world.step_count}
    elif args.planet:
        try:
            cfg, terrain, seed = load_planet(args.planet, build_config(args), args.seed)
        except PlanetError as e:
            raise SystemExit(f"Invalid planet: {e}") from e
        world = World(cfg, seed=seed, track_species=not args.no_species, terrain=terrain)
        meta = {"planet": args.planet}
    else:
        seed = 1 if args.seed is None else args.seed
        world = World(build_config(args), seed=seed, track_species=not args.no_species)
        meta = {}

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"seed": world.seed, **meta, **world.cfg.to_dict()}, f, indent=2)

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
            if args.save_every and st % args.save_every == 0:
                save_world(world, os.path.join(args.out, f"world_{st:06d}.json.gz"))
            if st % args.snap_every == 0:
                save_png(world, os.path.join(args.out, f"snap_{st:06d}.png"))
                s = world.stats()
                species = f" species={s['species']:4d} novelty={s['novelty']}" if "species" in s else ""
                print(f"[{st:6d}] pop={s['population']:5d} photo={s['photo']:5d} "
                      f"sapro={s['sapro']:5d} pred={s['pred']:5d} chemo={s['chemo']:4d} colony={s['in_colony']:5d} "
                      f"lineages={s['lineages']:3d} extinctions={s['extinctions']}{species} "
                      f"({time.time() - t0:.0f}s)", flush=True)
    elapsed = time.time() - t0

    save_world(world, os.path.join(args.out, "world_final.json.gz"))
    plot_stats(csv_path, os.path.join(args.out, "stats.png"))
    if world.tracker is not None:
        write_species_csv(world.tracker, os.path.join(args.out, "species.csv"))
        plot_species_tree(world.tracker, world.step_count, os.path.join(args.out, "species_tree.png"))
        plot_novelty(csv_path, os.path.join(args.out, "novelty.png"))
    print(f"Done: {args.out} ({args.steps / max(elapsed, 1e-9):.0f} steps/s)")


if __name__ == "__main__":
    main()
