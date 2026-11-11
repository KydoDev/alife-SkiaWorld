"""Save and load a complete world state (ADR-0002).

Format: gzip-compressed JSON, `{"format": "worldsim-save", "version": 8, ...}`.
Version 2 (F2, ADR-0004) added the static terrain maps and the 10th gene, version 3
(F3, ADR-0005) the 16-gene genome, version 4 (F4, ADR-0006) the per-cell rule genes,
version 5 (F5a, ADR-0007) the mating propensity and a sexual-births counter,
version 6 (F5b, ADR-0009) the acclimation rate and the acclimated diet, version 7 (F5c, ADR-0010)
the gene-transfer propensity and two transfer counters, version 8 (F5e, ADR-0011) the armour
and a repelled-attacks counter.
Older saves are rejected (their genomes cannot continue under the new rules).
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
from .world import N_GENES, RULE_LEN, Cell, World

FORMAT = "worldsim-save"
VERSION = 8
CELL_ROW_LEN = 15
MAX_SAVE_BYTES = 512 * 1024 * 1024     # decompressed size cap: guards against gzip bombs
COUNTERS = ("births", "deaths", "kills", "extinctions", "sex_births", "hgt_events", "hgt_foreign", "defended")


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
        "counters": {k: getattr(world, k) for k in COUNTERS},
        "rng": {"version": version, "internal": list(internal), "gauss_next": gauss_next},
        "organic": world.organic.tolist(),
        "terrain": _terrain_to_dict(world.terrain),
        # [id, x, y, energy, age, genes, lineage, species, [bond ids in insertion order], rules, sex_p, plast_p, diet,
        #  hgt_p, armor_p]
        "cells": [[c.id, c.x, c.y, c.energy, c.age, c.genes, c.lineage, c.species,
                   [b.id for b in c.bonds], [list(r) for r in c.rules], c.sex_p,
                   c.plast_p, list(c.diet), c.hgt_p, c.armor_p] for c in world.cells],
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
    """Rebuild a world from a save dict. Any malformed content raises SaveFormatError (saves are untrusted)."""
    try:
        return _world_from_dict(d)
    except SaveFormatError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, AttributeError) as e:
        raise SaveFormatError(f"malformed save: {type(e).__name__}: {e}") from e


def _world_from_dict(d: dict) -> World:
    if not isinstance(d, dict) or d.get("format") != FORMAT:
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
    if world.hgt_foreign > world.hgt_events:
        raise SaveFormatError("invalid counters: hgt_foreign exceeds hgt_events")
    rng = d["rng"]
    world.rng.setstate((rng["version"], tuple(rng["internal"]), rng["gauss_next"]))

    organic = np.asarray(d["organic"], dtype=np.float64)
    if not (np.isfinite(organic).all() and (organic >= 0).all()):
        raise SaveFormatError("organic field must be finite and non-negative")
    if organic.shape != (world.H, world.W):
        raise SaveFormatError(f"organic field has shape {organic.shape}, expected {(world.H, world.W)}")
    world.organic = organic

    by_id: dict[int, Cell] = {}
    if any(not isinstance(row, list) or len(row) != CELL_ROW_LEN for row in d["cells"]):
        raise SaveFormatError(f"every cell row must have {CELL_ROW_LEN} fields")
    for cid, x, y, energy, age, genes, lineage, species, _, rules, sex_p, plast_p, diet, hgt_p, armor_p in d["cells"]:
        if not (0 <= x < world.W and 0 <= y < world.H):
            raise SaveFormatError(f"cell #{cid} outside the grid at ({x}, {y})")
        if world.grid[y * world.W + x] is not None or world.blocked[y * world.W + x]:
            raise SaveFormatError(f"cell #{cid} on an occupied or rock tile at ({x}, {y})")
        valid = (len(genes) == N_GENES and cid not in by_id and _finite(energy)
                 and all(_finite(g) and 0.0 <= g <= 1.0 for g in genes))
        if not valid:
            raise SaveFormatError(f"invalid cell #{cid}")
        if not _valid_rules(rules, cfg):
            raise SaveFormatError(f"cell #{cid} has invalid rule genes")
        if not (_finite(sex_p) and 0.0 <= sex_p <= 1.0) or (sex_p and not cfg.sex):
            raise SaveFormatError(f"cell #{cid} has an invalid sex_p")
        if not (_finite(plast_p) and 0.0 <= plast_p <= 1.0) or (plast_p and not cfg.plasticity):
            raise SaveFormatError(f"cell #{cid} has an invalid plast_p")
        if not _valid_diet(diet, cfg):
            raise SaveFormatError(f"cell #{cid} has an invalid diet")
        if not (_finite(hgt_p) and 0.0 <= hgt_p <= 1.0) or (hgt_p and not cfg.hgt):
            raise SaveFormatError(f"cell #{cid} has an invalid hgt_p")
        if not (_finite(armor_p) and 0.0 <= armor_p <= 1.0) or (armor_p and not cfg.defence):
            raise SaveFormatError(f"cell #{cid} has an invalid armor_p")
        c = Cell(cid, x, y, energy, list(genes), lineage, cfg, [list(r) for r in rules], sex_p, plast_p, hgt_p,
                 armor_p)
        if cfg.plasticity:
            frozen = cfg.plastic_neutral or plast_p == 0.0      # such a diet never leaves the genetic split
            if frozen and any(abs(a - b) > 1e-9 for a, b in zip(diet, c.diet)):
                raise SaveFormatError(f"cell #{cid} has a diet that could not have moved")
            c.diet = tuple(diet)
            c.apply_diet(cfg)
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


def _valid_rules(rules, cfg) -> bool:
    """F4 rule genes: at most max_rules (none when the open genome is off), each RULE_LEN values in [0, 1]."""
    if not isinstance(rules, list) or len(rules) > (cfg.max_rules if cfg.open_genome else 0):
        return False
    return all(isinstance(r, list) and len(r) == RULE_LEN and all(_finite(v) and 0.0 <= v <= 1.0 for v in r)
               for r in rules)


def _valid_diet(diet, cfg) -> bool:
    """F5b diet: empty when plasticity is off, else 3 proportions in [0, 1] summing to 1 (within rounding)."""
    if not isinstance(diet, list):
        return False
    if not cfg.plasticity:
        return not diet
    return (len(diet) == 3 and all(_finite(v) and 0.0 <= v <= 1.0 for v in diet)
            and abs(sum(diet) - 1.0) < 1e-6)


def _finite(v) -> bool:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:           # a huge JSON integer
        return False


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
