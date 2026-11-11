"""G2 golden vectors for world creation (ADR-0012 piece 4): the step-0 state hash of `World(cfg, seed)` with
generated terrain, on every procedural-terrain case of g2_terrain_vectors.py plus the founder flags and the
edge cases of `initial_cells`. Each case carries the full `cfg.to_dict()` (the save's `config` object, the
input of the kernel's `World::new`). Terrain uses libm, so `g2_golden.py --all ROOT` writes this file as
ROOT/create.json and CI regenerates it on Linux. Checked by engine-rs/tests/golden_create.rs.

    python scripts/g2_create_vectors.py --out engine-rs/tests/golden/create.json
"""
import argparse
import functools
import importlib.util
import json
import platform
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from worldsim.config import Config  # noqa: E402
from worldsim.world import World  # noqa: E402

FOUNDER_FLAGS = ("sex", "plasticity", "hgt", "defence", "open_genome")


def _sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.cache
def _golden():
    return _sibling("g2_golden")


def create_specs():
    """(name, Config fields, seed): every terrain case, then flags and `initial_cells` edge cases."""
    tv = _sibling("g2_terrain_vectors")
    out = []
    for name, params, seeds in tv.terrain_specs():
        cells = min(Config().initial_cells, params["width"] * params["height"])
        out += [(name, {**params, "initial_cells": cells}, seed) for seed in seeds]
    volcanic = next(p for n, p, _ in tv.terrain_specs() if n == "volcanic")
    out += [(f"flag_{flag}", {**volcanic, flag: True}, 42) for flag in FOUNDER_FLAGS]
    out.append(("flag_all", {**volcanic, **{flag: True for flag in FOUNDER_FLAGS}}, 42))
    out.append(("no_founders", {**volcanic, "initial_cells": 0}, 42))
    dense = next(p for n, p, _ in tv.terrain_specs() if n == "dense")
    out.append(("founders_above_free_tiles", {**dense, "initial_cells": 6000}, 1))
    return out


def create_case(name, fields, seed) -> dict:
    cfg = Config(**fields).validate()
    world = World(cfg, seed=seed, track_species=False)
    free = sum(1 for b in world.blocked if not b)
    return {"name": name, "seed": str(seed), "config": cfg.to_dict(), "hash": _golden().state_hash(world),
            "population": len(world.cells), "free_tiles": free, "rock_tiles": len(world.blocked) - free,
            "vents": bool(world.has_chem), "next_id": world.next_id}


def build() -> dict:
    return {"system": platform.system(), "python": platform.python_version(),
            "cases": [create_case(*spec) for spec in create_specs()]}


def write(out: Path) -> None:
    doc = build()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{out}: {len(doc['cases'])} creations")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    write(ap.parse_args(argv).out)


if __name__ == "__main__":
    main()
