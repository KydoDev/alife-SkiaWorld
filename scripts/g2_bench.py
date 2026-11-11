r"""G2 milestone M3: benchmark worlds for the Rust kernel, and the Python baseline on the same worlds.

For each size it writes `<out>/<name>.json.gz`, a save at step 0 (default flags, no species tracker, larger
world and initial population), times `--py-steps` Python steps on it and records the population and state hash
after them in `<out>/bench.json`. The Rust benchmark (`cargo run --release --example bench -- <out>`) steps the
same saves, checks its hash after the same number of steps, and reports cell-updates per second.

    python scripts/g2_bench.py --out engine-rs/target/bench
"""
import argparse
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from worldsim.config import Config  # noqa: E402
from worldsim.persistence import save_world  # noqa: E402
from worldsim.world import World  # noqa: E402

_spec = importlib.util.spec_from_file_location("g2_golden", ROOT / "scripts" / "g2_golden.py")
g2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g2)

# The default world is light-limited at ~700 cells (a few per column), so the large worlds let light reach
# deeper and feed more (RICH); otherwise a 50k start collapses to ~5k cells and the benchmark mostly times the
# O(W*H) field passes of a near-empty grid. Throughput, not ecology, is what M3 measures.
RICH = {"light_depth": 1000.0, "shade": 0.97, "photo_gain": 4.0}
# name, width, height, initial cells, config overrides, Python steps timed (fewer where Python is slow)
SIZES = (("800", 160, 64, 800, {}, 200),
         ("10k", 400, 160, 10_000, RICH, 40),
         ("50k", 800, 320, 50_000, RICH, 10))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    report = {"python": platform.python_version(), "platform": platform.platform(), "worlds": []}
    for name, width, height, cells, overrides, steps in SIZES:
        cfg = Config(width=width, height=height, initial_cells=cells, **overrides)
        world = World(cfg, seed=args.seed, track_species=False)
        save_world(world, args.out / f"{name}.json.gz")
        updates = 0
        t0 = time.perf_counter()
        for _ in range(steps):
            updates += len(world.cells)          # cells processed by this step
            world.step()
        dt = time.perf_counter() - t0
        row = {"name": name, "width": width, "height": height, "initial_cells": cells, "overrides": overrides,
               "steps": steps,
               "cell_updates": updates, "seconds": dt, "updates_per_s": updates / dt,
               "final_population": len(world.cells), "final_hash": g2.state_hash(world)}
        report["worlds"].append(row)
        print(f"{name}: Python {steps} steps, {updates / dt:,.0f} cell-updates/s "
              f"({steps / dt:.1f} steps/s), population {cells} -> {len(world.cells)}")
    (args.out / "bench.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
