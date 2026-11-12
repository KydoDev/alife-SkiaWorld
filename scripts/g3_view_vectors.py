"""G3 P4 golden vectors of the kernel's read-only views (ADR-0016), from Python's reference `worldsim/views.py`.

For each set in SETS, at its golden start save and after STEPS more steps: the SHA-256 of `tile_words`, the
light factor, the state hash, and the inspector records of up to MAX_CELLS cells picked by a fixed rule (in grid
order: the first, the last, then the bonded ones). Floats are IEEE-754 bit patterns (hex), so the comparison is exact.
The Rust tests (`engine-rs/tests/golden_views.rs`) and the Unity EditMode tests read the file. Like the other golden
vectors it depends on the platform's libm (`volcanic` steps through sin), so `scripts/g2_golden.py --all` regenerates
it with them (CI does so on Linux); on its own, from a golden root holding the start saves:

    python scripts/g3_view_vectors.py --root engine-rs/tests/golden --out engine-rs/tests/golden/views.json
"""
import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from worldsim.persistence import load_world  # noqa: E402
from worldsim.views import cell_record, tile_words  # noqa: E402

GOLDEN = ROOT / "engine-rs/tests/golden"
# default (flat, no flags), volcanic (rock, vents, day and season), plasticity (acclimated shares, many bonds),
# combined (every ported flag, so every trait is non-zero somewhere)
SETS = ("default", "volcanic", "plasticity", "combined")
STEPS = 37
MAX_CELLS = 8


def _golden_module():
    spec = importlib.util.spec_from_file_location("g2_golden", ROOT / "scripts/g2_golden.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def picked_cells(world) -> list[tuple[int, int]]:
    """Tiles of the cells to record: the first and last occupied tile in grid order, then bonded cells."""
    occupied = [(i % world.W, i // world.W) for i, c in enumerate(world.grid) if c is not None]
    bonded = [(i % world.W, i // world.W) for i, c in enumerate(world.grid) if c is not None and c.bonds]
    picked = []
    for xy in [occupied[0], occupied[-1], *bonded]:
        if xy not in picked:
            picked.append(xy)
        if len(picked) == MAX_CELLS:
            break
    return picked


def snapshot(world, f64_hex, state_hash) -> dict:
    cells = []
    for x, y in picked_cells(world):
        r = cell_record(world, x, y)
        cells.append({"x": x, "y": y, **{k: r[k] for k in ("id", "lineage", "age", "bonds", "colony", "rules")},
                      "energy": f64_hex(r["energy"]), "genes": [f64_hex(v) for v in r["genes"]],
                      "shares": [f64_hex(v) for v in r["shares"]], "traits": [f64_hex(v) for v in r["traits"]]})
    return {"step": world.step_count, "tiles_sha256": hashlib.sha256(tile_words(world)).hexdigest(),
            "light_factor": f64_hex(world.light_factor(world.step_count)), "state_hash": state_hash(world),
            "cells": cells}


def build(root: Path) -> dict:
    g2 = _golden_module()
    cases = []
    for name in SETS:
        world = load_world(root / name / "start.json.gz")
        start = snapshot(world, g2.f64_hex, g2.state_hash)
        for _ in range(STEPS):
            world.step()
        cases.append({"set": name, "snapshots": [start, snapshot(world, g2.f64_hex, g2.state_hash)]})
    return {"system": platform.system(), "python": platform.python_version(), "steps": STEPS, "cases": cases}


def write(root: Path, out: Path) -> None:
    doc = build(root)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"{out}: view vectors of {len(doc['cases'])} sets")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=GOLDEN, help="golden root holding the start saves")
    ap.add_argument("--out", type=Path, default=GOLDEN / "views.json")
    args = ap.parse_args(argv)
    write(args.root, args.out)


if __name__ == "__main__":
    main()
