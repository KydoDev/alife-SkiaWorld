"""G2 golden vectors for procedural terrain (ADR-0012 piece 3) and for `vent_plume` (ADR-0013 piece 1).

`generate_terrain` uses libm `sin` and `exp`, so the digests depend on the platform maths library like the
stepped golden hashes: `g2_golden.py --all ROOT` writes this file as ROOT/terrain.json next to the sets, the
committed copy is the Windows reference and CI regenerates it on Linux. Checked by
engine-rs/tests/terrain_vectors.rs.

    python scripts/g2_terrain_vectors.py --out engine-rs/tests/golden/terrain.json
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from worldsim.config import Config  # noqa: E402
from worldsim.terrain import generate_terrain, vent_plume  # noqa: E402
from worldsim.worldgen import config_from_form  # noqa: E402

PARAMS = ("width", "height", "organic_init", "rock_fraction", "vent_count", "vent_strength", "vent_radius")
BASE = {"width": 160, "height": 64, "organic_init": 0.0, "rock_fraction": 0.0, "vent_count": 0,
        "vent_strength": 2.0, "vent_radius": 4.0}
WIDTHS = (2, 7, 8, 9, 127, 128, 129, 257, 10_000)
U64_MAX = 2**64 - 1


def _volcanic():
    form = json.loads((REPO / "examples" / "volcanic.json").read_text(encoding="utf-8"))
    cfg, seed = config_from_form(form)
    return {k: getattr(cfg, k) for k in PARAMS}, seed


def terrain_specs():
    """(name, params, seeds): the cases of the ADR-0012 piece 3 verdict."""
    volcanic, volcanic_seed = _volcanic()
    specs = [
        ("default", {}, [1]),
        ("flat_organic", {"organic_init": 0.5}, [1]),
        ("rock_only", {"rock_fraction": 0.3, "organic_init": 0.25}, [1, 2, U64_MAX]),
        ("vents_only", {"vent_count": 4}, [1, 2, 3]),
        ("vents_without_strength", {"rock_fraction": 0.3, "vent_count": 4, "vent_strength": 0.0}, [1]),
        ("volcanic", volcanic, [volcanic_seed, 1, 2]),
        ("dense", {"rock_fraction": 0.9, "vent_count": 100, "organic_init": 1.0}, [1, 2, 3]),
        ("tiny_radius", {"rock_fraction": 0.2, "vent_count": 3, "vent_radius": 1e-6}, [1]),
    ]
    specs += [(f"width_{w}", {"width": w, "height": 100, "rock_fraction": 0.4, "vent_count": 5}, [1, 2, 3])
              for w in WIDTHS]
    specs.append(("largest", {"width": 10_000, "height": 100, "rock_fraction": 0.5, "vent_count": 100}, [7]))
    return [(name, {**BASE, **over}, seeds) for name, over, seeds in specs]


def _digest(arr, dtype) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr, dtype=dtype).tobytes()).hexdigest()


def terrain_case(name, params, seed) -> dict:
    cfg = Config(**params, initial_cells=1).validate()
    t = generate_terrain(cfg, seed)
    return {"name": name, "seed": str(seed), "params": params,
            "rock": _digest(t.rock, np.uint8), "chem": _digest(t.chem, "<f8"),
            "sun": _digest(t.sun, "<f8"), "organic": _digest(t.organic, "<f8"),
            "rock_tiles": int(t.rock.sum()), "chem_tiles": int(np.count_nonzero(t.chem))}


def plume_specs():
    """(W, H, vx, vy, strength, radius): corners and centre, three widths, `exp` underflow, volcanic values."""
    volcanic, _ = _volcanic()
    out = []
    for w, h in ((2, 5), (7, 9), (128, 64)):
        for vx, vy in ((0, 0), (w - 1, h - 1), (w // 2, h // 2)):
            for strength, radius in ((2.0, 4.0), (2.0, 1e-6), (volcanic["vent_strength"], volcanic["vent_radius"])):
                out.append((w, h, vx, vy, strength, radius))
    return out


def plume_case(w, h, vx, vy, strength, radius) -> dict:
    plume = vent_plume(h, w, vx, vy, strength, radius)
    return {"width": w, "height": h, "vx": vx, "vy": vy, "strength": strength, "radius": radius,
            "plume": _digest(plume, "<f8"), "nonzero": int(np.count_nonzero(plume))}


def build() -> dict:
    return {"system": platform.system(), "python": platform.python_version(), "numpy": np.__version__,
            "terrain": [terrain_case(n, p, s) for n, p, seeds in terrain_specs() for s in seeds],
            "plumes": [plume_case(*spec) for spec in plume_specs()]}


def write(out: Path) -> None:
    doc = build()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{out}: {len(doc['terrain'])} terrains, {len(doc['plumes'])} plumes")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    write(ap.parse_args(argv).out)


if __name__ == "__main__":
    main()
