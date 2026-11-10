"""Save and load a complete world state (ADR-0002).

Format: gzip-compressed JSON, `{"format": "worldsim-save", "version": 2, ...}`.
Version 2 (F2, ADR-0004) adds the static terrain maps and the 10th gene; version-1
saves are rejected (their 9-gene genomes cannot continue under the new rules).
JSON is used instead of pickle so a save file shared by someone else can never
execute code when loaded. Python's float repr round-trips exactly through JSON,
so a resumed run continues bit-for-bit like an uninterrupted one.

Everything the dynamics depend on is stored verbatim: the RNG state (including
the cached Gaussian), the order of `World.cells` (the step shuffles it in place)
and the insertion order of every `Cell.bonds` (energy sharing iterates it).
"""
import gzip
import json
import math

import numpy as np

from .config import Config
from .species import SpeciesTracker
from .terrain import Terrain
from .world import N_GENES, Cell, World

FORMAT = "worldsim-save"
VERSION = 3
MAX_SAVE_BYTES = 512 * 1024 * 1024     # decompressed size cap: guards against gzip bombs
COUNTERS = ("births", "deaths", "kills", "extinctions")


class SaveFormatError(ValueError):
    pass


def world_to_dict(world: World) -> dict:
    version, internal, gauss_next = world.rng.getstate()
    return {
        "format": FORMAT,
        "version": VERSION,
        "config": world.cfg.to_dict(),
        "seed": world.seed,
        "step_count": world.step_count,
        "next_id": world.next_id,
        "counters": {"births": world.births, "deaths": world.deaths,
                     "kills": world.kills, "extinctions": world.extinctions},
        "rng": {"version": version, "internal": list(internal), "gauss_next": gauss_next},
        "organic": world.organic.tolist(),
        "terrain": _terrain_to_dict(world.terrain),
        # [id, x, y, energy, age, genes, lineage, species, [bond ids in insertion order]]
        "cells": [[c.id, c.x, c.y, c.energy, c.age, c.genes, c.lineage, c.species,
                   [b.id for b in c.bonds]] for c in world.cells],
        "tracker": world.tracker.to_dict() if world.tracker is not None else None,
    }


def _terrain_to_dict(t: Terrain) -> dict | None:
    if t.is_flat:
        return None                                   # flat world: nothing to store
    return {"rock": t.rock.astype(np.uint8).tolist(), "chem": t.chem.tolist(), "sun": t.sun.tolist()}


def _terrain_from_dict(d: dict | None, width: int, height: int) -> Terrain:
    terrain = Terrain.flat(width, height)
    if d is None:
        return terrain
    try:
        rock = np.asarray(d["rock"], dtype=np.int64)
        terrain.chem = np.asarray(d["chem"], dtype=np.float64)
        terrain.sun = np.asarray(d["sun"], dtype=np.float64)
    except (KeyError, TypeError, ValueError, OverflowError) as e:
        raise SaveFormatError(f"invalid terrain: {e}") from e
    if not np.isin(rock, (0, 1)).all():
        raise SaveFormatError("terrain rock map must contain only 0 and 1")
    terrain.rock = rock.astype(bool)
    if (terrain.rock.shape, terrain.chem.shape, terrain.sun.shape) != ((height, width), (height, width), (width,)):
        raise SaveFormatError(f"terrain maps do not match the {width}x{height} world")
    for name in ("chem", "sun"):
        m = getattr(terrain, name)
        if not (np.isfinite(m).all() and (m >= 0).all()):
            raise SaveFormatError(f"terrain {name} map must be finite and non-negative")
    return terrain


def world_from_dict(d: dict) -> World:
    if d.get("format") != FORMAT:
        raise SaveFormatError("not a WorldSim save file")
    if d.get("version") != VERSION:
        raise SaveFormatError(f"unsupported save version {d.get('version')!r} (expected {VERSION})")

    try:
        cfg = Config(**d["config"]).validate()   # unknown keys raise TypeError
    except (TypeError, ValueError) as e:
        raise SaveFormatError(f"invalid config: {e}") from e
    terrain = _terrain_from_dict(d.get("terrain"), cfg.width, cfg.height)
    world = World(cfg, seed=d["seed"], track_species=d["tracker"] is not None, populate=False,
                  terrain=terrain)
    world.step_count = d["step_count"]
    world.now = world.step_count
    world.next_id = d["next_id"]
    for k in COUNTERS:                       # whitelist: a save must not overwrite other attributes
        v = d["counters"].get(k)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise SaveFormatError(f"invalid counter {k!r}")
        setattr(world, k, v)
    rng = d["rng"]
    world.rng.setstate((rng["version"], tuple(rng["internal"]), rng["gauss_next"]))

    organic = np.asarray(d["organic"], dtype=np.float64)
    if not (np.isfinite(organic).all() and (organic >= 0).all()):
        raise SaveFormatError("organic field must be finite and non-negative")
    if organic.shape != (world.H, world.W):
        raise SaveFormatError(f"organic field has shape {organic.shape}, expected {(world.H, world.W)}")
    world.organic = organic

    by_id: dict[int, Cell] = {}
    for cid, x, y, energy, age, genes, lineage, species, _ in d["cells"]:
        if not (0 <= x < world.W and 0 <= y < world.H):
            raise SaveFormatError(f"cell #{cid} outside the grid at ({x}, {y})")
        if world.grid[y * world.W + x] is not None or world.blocked[y * world.W + x]:
            raise SaveFormatError(f"cell #{cid} on an occupied or rock tile at ({x}, {y})")
        valid = (len(genes) == N_GENES and cid not in by_id and _finite(energy)
                 and all(_finite(g) and 0.0 <= g <= 1.0 for g in genes))
        if not valid:
            raise SaveFormatError(f"invalid cell #{cid}")
        c = Cell(cid, x, y, energy, list(genes), lineage, cfg)
        c.age = age
        c.species = species
        world._place(c)
        by_id[cid] = c
    for row in d["cells"]:
        cell = by_id[row[0]]
        for bid in row[8]:
            if bid not in by_id:
                raise SaveFormatError(f"cell #{row[0]} bonded to missing cell #{bid}")
            cell.bonds[by_id[bid]] = None

    if d["tracker"] is not None:
        world.tracker = _load_tracker(d["tracker"], by_id.values())
    world.update_light()
    return world


def save_world(world: World, path) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(world_to_dict(world), f, separators=(",", ":"))


def _load_tracker(data, cells) -> SpeciesTracker:
    """Rebuild the species tracker and check it against the cells, so that a hostile or stale save
    fails here rather than at the first birth or death."""
    tracker = SpeciesTracker.from_dict(data)
    for s in tracker.species.values():
        genes = s.founder_genes
        if len(genes) != N_GENES or not all(_finite(g) and 0.0 <= g <= 1.0 for g in genes):
            raise SaveFormatError(f"species #{s.id} has an invalid founder genome")
    for c in cells:
        if c.species not in tracker.extant:
            raise SaveFormatError(f"cell #{c.id} belongs to unknown or extinct species {c.species!r}")
    return tracker


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def load_world(path) -> World:
    with gzip.open(path, "rb") as f:
        data = f.read(MAX_SAVE_BYTES + 1)
    if len(data) > MAX_SAVE_BYTES:
        raise SaveFormatError(f"save decompresses to more than {MAX_SAVE_BYTES} bytes")
    try:
        d = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise SaveFormatError(f"not a valid save file: {e}") from e
    return world_from_dict(d)
