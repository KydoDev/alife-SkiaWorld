r"""G2 golden vectors: reference data the Rust port (engine-rs/) must reproduce bit-for-bit.

Writes into --out:
- start.json.gz  a save (current format) after --warmup steps (default flags, no species tracker);
- rng.json       draws from CPython's random.Random, floats stored as IEEE-754 bit patterns (hex);
- hashes.csv     step,hash for each of the --steps steps that follow the save;
- render_start.rgb.gz / render_end.rgb.gz  `render_rgb` of the loaded start save and of the world after
  the last step (raw RGB, row 0 = surface; gzip without timestamp). `--renders-only` writes just these two
  from an existing start.json.gz, leaving the other files untouched;
- step_N.json.gz with --dump-step N, a save at step N, so a mismatching kernel can name the first
  field that differs (engine-rs/tests/golden_step.rs reads it from engine-rs/target/g2-dumps/<set>/).

The state hash is defined in docs/G2_PLAN.md ("State hash"); both engines must implement it byte-for-byte.
Golden files depend on the platform's maths library for gauss/pow/sin, so they record where they were made.

Every golden set is listed in SETS below, the single list that pytest, the Rust tests and CI follow;
`--all ROOT` (re)writes each of them under ROOT/<name>:

    python scripts/g2_golden.py --all engine-rs/tests/golden
    python scripts/g2_golden.py --planet examples/volcanic.json --set defence=1 --out engine-rs/target/try
"""
import argparse
import csv
import gzip
import hashlib
import json
import platform
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worldsim.config import Config  # noqa: E402
from worldsim.persistence import COUNTERS, VERSION, load_world, save_world  # noqa: E402
from worldsim.render import render_rgb  # noqa: E402
from worldsim.world import World  # noqa: E402
from worldsim.worldgen import load_planet  # noqa: E402

RANDRANGE_NS = (1, 2, 3, 7, 10, 100, 1000, 10_240, 2**31 - 1, 2**32 + 5)
REPO = Path(__file__).resolve().parent.parent
# The golden sets: name -> arguments added to SET_COMMON. Planet paths are relative to the repository.
SET_COMMON = ["--seed", "1", "--warmup", "200", "--steps", "1000"]
SETS = {
    "default": [],
    "volcanic": ["--planet", "examples/volcanic.json"],
    "defence": ["--set", "defence=1"],
    "defence_neutral": ["--set", "defence=1", "--set", "defence_neutral=1"],
    "hgt": ["--set", "hgt=1"],
    "hgt_neutral": ["--set", "hgt=1", "--set", "hgt_neutral=1"],
    "plasticity": ["--set", "plasticity=1"],
    "plastic_neutral": ["--set", "plasticity=1", "--set", "plastic_neutral=1"],
}


def f64_hex(v: float) -> str:
    return struct.pack("<d", v).hex()


def state_hash(world: World) -> str:
    """SHA-256 of the dynamic state, little-endian, in the order fixed by docs/G2_PLAN.md."""
    h = hashlib.sha256()
    u64 = struct.Struct("<Q").pack
    u32 = struct.Struct("<I").pack
    f64 = struct.Struct("<d").pack
    h.update(u64(world.step_count) + u64(world.next_id))
    for n in (world.births, world.deaths, world.kills, world.extinctions, world.sex_births):
        h.update(u64(n))
    # flag fields are hashed only when their flag is on (M5)
    plastic, hgt, defence = world.cfg.plasticity, world.cfg.hgt, world.cfg.defence
    if hgt:
        h.update(u64(world.hgt_events) + u64(world.hgt_foreign))
    if defence:
        h.update(u64(world.defended))
    _, internal, gauss_next = world.rng.getstate()
    h.update(struct.pack(f"<{len(internal)}I", *internal))      # 624 MT words + position index
    h.update(b"\x00" + f64(0.0) if gauss_next is None else b"\x01" + f64(gauss_next))
    h.update(world.organic.astype("<f8", copy=False).tobytes(order="C"))
    h.update(u64(len(world.cells)))
    for c in world.cells:
        h.update(u64(c.id) + u32(c.x) + u32(c.y) + f64(c.energy) + u64(c.age))
        h.update(struct.pack("<16d", *c.genes))
        h.update(u64(c.lineage) + u64(len(c.bonds)))
        for b in c.bonds:
            h.update(u64(b.id))
        h.update(f64(c.sex_p))
        if plastic:
            h.update(f64(c.plast_p) + struct.pack("<3d", *c.diet))
        if hgt:
            h.update(f64(c.hgt_p))
        if defence:
            h.update(f64(c.armor_p))
    return h.hexdigest()


def write_render(world: World, path: Path) -> None:
    """Raw RGB bytes of `render_rgb`, gzip with mtime 0 so regenerating gives identical files."""
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as f:
        f.write(render_rgb(world).tobytes(order="C"))


def write_renders(out: Path, steps: int) -> None:
    """Render the loaded start save and the world `steps` steps later; check the final hash."""
    world = load_world(out / "start.json.gz")
    write_render(world, out / "render_start.rgb.gz")
    for _ in range(steps):
        world.step()
    with open(out / "hashes.csv", encoding="utf-8") as f:
        last = list(csv.reader(f))[-1]
    if [str(world.step_count), state_hash(world)] != [last[0], last[2]]:
        raise SystemExit(f"{out}: the loaded save does not reproduce hashes.csv; regenerate the set")
    write_render(world, out / "render_end.rgb.gz")


def rng_vectors(seed: int) -> dict:
    """Draws from a fresh random.Random(seed), covering every method the engine uses."""
    rng = random.Random(seed)
    start = list(rng.getstate()[1])
    out = {"seed": seed, "start_state": start}
    out["random"] = [f64_hex(rng.random()) for _ in range(1000)]
    out["randrange"] = {str(n): [rng.randrange(n) for _ in range(20)] for n in RANDRANGE_NS}
    shuffles = []
    for _ in range(3):
        xs = list(range(50))
        rng.shuffle(xs)
        shuffles.append(xs)
    out["shuffle_50"] = shuffles
    out["choice_9"] = [rng.choice(range(9)) for _ in range(50)]
    # gauss caches its second value (gauss_next): interleave with random() so the cache is exercised
    seq = []
    for i in range(1000):
        if i % 4 == 3:                     # after an odd number of gauss calls: a cached value is pending
            seq.append(["r", f64_hex(rng.random())])
        else:
            seq.append(["g", f64_hex(rng.gauss(0.0, 0.05))])
    out["mixed_gauss_random"] = seq
    out["end_state"] = list(rng.getstate()[1])
    return out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--warmup", type=int, default=200, help="steps run before the start save")
    ap.add_argument("--steps", type=int, default=1000, help="steps hashed after the start save")
    ap.add_argument("--planet", type=Path, help="planet form (.json) or image; default: the flat default world")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override a Config parameter (as run.py); a planet form's fields override it")
    ap.add_argument("--out", type=Path, help="directory of the set to write")
    ap.add_argument("--all", type=Path, metavar="ROOT", help="write every set of SETS under ROOT/<name>")
    ap.add_argument("--dump-step", type=int, help="also write a save at this step (step_N.json.gz)")
    ap.add_argument("--renders-only", action="store_true", help="only (re)write the two golden renders")
    return ap


def main(argv=None, repo_relative=False) -> None:
    """`repo_relative`: resolve --planet against the repository only (used by --all for the paths in SETS)."""
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.all:
        defaults = ap.parse_args([])
        own = [k for k in ("out", "planet", "set", "dump_step", "seed", "warmup", "steps")
               if getattr(args, k) != getattr(defaults, k)]
        if own:
            flags = ", ".join("--" + k.replace("_", "-") for k in own)
            ap.error(f"--all takes each set's arguments from SETS; drop {flags}")
        renders = ["--renders-only"] if args.renders_only else []
        for name, extra in SETS.items():
            main([*SET_COMMON, *extra, "--out", str(args.all / name), *renders], repo_relative=True)
        return
    if args.out is None:
        ap.error("--out or --all is required")
    if args.renders_only:
        write_renders(args.out, args.steps)
        print(f"{args.out}: renders written")
        return
    if args.steps < 1 or args.warmup < 0:
        ap.error("--steps must be >= 1 and --warmup >= 0")

    try:
        cfg = Config().apply_overrides(args.set).validate()
    except ValueError as e:
        ap.error(f"invalid --set: {e}")
    args.out.mkdir(parents=True, exist_ok=True)
    if args.planet:
        planet = REPO / args.planet if repo_relative or not args.planet.exists() else args.planet
        cfg, terrain, seed = load_planet(planet, cfg, args.seed)
        world = World(cfg, seed=seed, track_species=False, terrain=terrain)
    else:
        world = World(cfg, seed=args.seed, track_species=False)
    for _ in range(args.warmup):
        world.step()
    save_world(world, args.out / "start.json.gz")
    start_hash = state_hash(world)
    start_counts = {name: getattr(world, name) for name in COUNTERS}

    with open(args.out / "hashes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["step", "population", "hash"])
        w.writerow([world.step_count, len(world.cells), start_hash])
        for _ in range(args.steps):
            world.step()
            w.writerow([world.step_count, len(world.cells), state_hash(world)])
            if world.step_count == args.dump_step:
                save_world(world, args.out / f"step_{args.dump_step}.json.gz")

    rng = rng_vectors(args.seed)
    rng["meta"] = {"python": platform.python_version(), "system": platform.system(), "platform": platform.platform(),
                   "save_version": VERSION, "warmup": args.warmup, "steps": args.steps,
                   "planet": args.planet.as_posix() if args.planet else None, "set": args.set,
                   # events during the hashed steps: shows that a flag's mechanism actually fired
                   "counter_deltas": {name: getattr(world, name) - n for name, n in start_counts.items()}}
    (args.out / "rng.json").write_text(json.dumps(rng, separators=(",", ":")) + "\n", encoding="utf-8")
    write_renders(args.out, args.steps)
    print(f"{args.out}: start step {args.warmup} hash {start_hash[:12]}, "
          f"{args.steps} steps, final population {len(world.cells)}")


if __name__ == "__main__":
    main()
