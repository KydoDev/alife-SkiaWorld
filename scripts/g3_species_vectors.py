"""G3 P8 golden vectors of the species tracker (ADR-0018), from Python's reference `worldsim/species.py`.

Each case runs a world with species tracking on, as the kernel will: created from a config and a seed (what
`ws_world_create` takes), or loaded from a tracked save (`species_start.json.gz`, written here into the golden root),
optionally with a G1 game whose actions kill cells. Every SAMPLE_EVERY steps and at the end it records the state hash
(which must equal the same run with tracking off: the tracker is an observer, ADR-0003), a digest of the tracker, a
digest of every living cell's species and the SHA-256 of the tile words (whose key is the species id when tracked).
At the end it also records the tracker's full `to_dict()` (founder genes as IEEE-754 bit patterns) and each cell's
`[id, species]`, so a port that differs can be told which field.

Tracker digest: SHA-256 over little-endian u64 `next_id, speciations, novelty, pruned`, then for each retained species
in id order: u64 `id, parent (0 = none), origin (0 seed, 1 immigrant, 2 speciation), born, extinct (u64::MAX = none),
count, peak, activity, established (u64::MAX = none), children`, then its founder genes as f64. Cells digest: SHA-256
over u64 `id, species` per living cell in id order.

The generator asserts the verdict's non-vacuous conditions (speciation, extinction, pruning, novelty, an immigrant
root, a species driven extinct by an intervention, a reseed after extinction). Values depend on libm (`volcanic`), so
`scripts/g2_golden.py --all` writes this file with the others. On its own:

    python scripts/g3_species_vectors.py --root engine-rs/tests/golden --out engine-rs/tests/golden/species.json
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import platform
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from worldsim.config import Config  # noqa: E402
from worldsim.persistence import load_world, world_to_dict  # noqa: E402
from worldsim.play import Game, GameRules  # noqa: E402
from worldsim.species import ORIGIN_IMMIGRANT, ORIGIN_SEED, ORIGIN_SPECIATION  # noqa: E402
from worldsim.views import tile_words  # noqa: E402
from worldsim.world import World  # noqa: E402
from worldsim.worldgen import load_planet  # noqa: E402

GOLDEN = ROOT / "engine-rs/tests/golden"
SAMPLE_EVERY = 100
START_SAVE = "species_start.json.gz"
SAVE_SEED, SAVE_STEPS = 3, 300          # the tracked start save: Config(), this seed, this many steps
ORIGINS = (ORIGIN_SEED, ORIGIN_IMMIGRANT, ORIGIN_SPECIATION)
NONE_U64 = 2**64 - 1
_BIG = dict(budget_start=1e6, budget_max=1e6)


def _volcanic():
    cfg, _terrain, seed = load_planet(ROOT / "examples/volcanic.json", Config(), 42)
    return cfg.to_dict(), seed


def case_specs():
    """(name, config fields or None for the tracked save, seed, warmup before the game, rules, log, steps)."""
    volcanic, volcanic_seed = _volcanic()
    flags = dict(sex=True, hgt=True, plasticity=True, defence=True)
    meteorites = [(30, "meteorite", x, y) for x in range(0, 160, 20) for y in (8, 30, 52)]
    return [
        ("created_default", {}, 1, 0, None, [], 1000),
        ("created_volcanic", volcanic, volcanic_seed, 0, None, [], 1000),
        ("created_flags", flags, 7, 0, None, [], 1000),
        # tiny, no immigrants, short lives: life dies out and is reseeded (as the `combined_reseed` golden set)
        ("created_reseed", dict(width=4, height=4, initial_cells=8, immigration_rate=0, max_age=30), 1, 0, None, [],
         300),
        ("tracked_save", None, SAVE_SEED, 0, None, [], 700),
        # the `survivor` script of games.json on a tracked world: meteorites kill whole species
        ("game_meteorites", {}, 1, 200, GameRules(collapse_window=50, **_BIG), meteorites, 400),
    ]


def _golden_module():
    spec = importlib.util.spec_from_file_location("g2_golden", ROOT / "scripts/g2_golden.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _opt(v):
    return NONE_U64 if v is None else v


def tracker_digest(t) -> str:
    h = hashlib.sha256(struct.pack("<4Q", t.next_id, t.speciations, t.novelty, t.pruned))
    for sid in sorted(t.species):
        s = t.species[sid]
        h.update(struct.pack("<10Q", s.id, s.parent or 0, ORIGINS.index(s.origin), s.born, _opt(s.extinct),
                             s.count, s.peak, s.activity, _opt(s.established), s.children))
        h.update(struct.pack(f"<{len(s.founder_genes)}d", *s.founder_genes))
    return h.hexdigest()


def cells_digest(world) -> str:
    h = hashlib.sha256()
    for c in sorted(world.cells, key=lambda c: c.id):
        h.update(struct.pack("<2Q", c.id, c.species))
    return h.hexdigest()


def tracker_dump(t, g2) -> dict:
    d = t.to_dict()
    d["threshold"] = g2.f64_hex(float(d["threshold"]))
    d["species"] = [[*row[:3], [g2.f64_hex(float(v)) for v in row[3]], *row[4:]]
                    for row in sorted(d["species"], key=lambda r: r[0])]
    return d


def start_save_bytes() -> bytes:
    """The tracked save the `tracked_save` case loads (and the kernel's tracker loader is checked on), as
    `save_world` writes it but gzipped with mtime 0, so regenerating gives identical bytes."""
    world = World(Config(), seed=SAVE_SEED)
    for _ in range(SAVE_STEPS):
        world.step()
    text = json.dumps(world_to_dict(world), separators=(",", ":")).encode("utf-8")
    return gzip.compress(text, mtime=0)


def write_start_save(root: Path) -> None:
    (root / START_SAVE).write_bytes(start_save_bytes())


def _world(fields, seed, root: Path, track: bool):
    if fields is None:
        world = load_world(root / START_SAVE)
        if not track:
            world.tracker = None
        return world
    return World(Config(**fields), seed=seed, track_species=track)


class _Run:
    """One case run: the world, its game if any, and the steps and actions it went through."""

    def __init__(self, spec, root: Path, track: bool):
        name, fields, seed, warmup, rules, log, steps = spec
        self.world = _world(fields, seed, root, track)
        for _ in range(warmup):
            self.world.step()
        self.game = Game(self.world, rules) if rules is not None else None
        self.pending = sorted(log, key=lambda a: a[0])
        self.steps = steps
        self.killed_by_action = 0       # species driven extinct inside an action

    def act_due(self, k):
        while self.pending and self.pending[0][0] <= k:
            _offset, tool, x, y = self.pending.pop(0)
            t = self.world.tracker
            before = set(t.extant) if t is not None else set()
            self.game.act(tool, x, y)
            if t is not None:
                self.killed_by_action += len(before - set(t.extant))

    def step(self):
        if self.game is not None:
            self.game.step()
        else:
            self.world.step()


def run_case(spec, root: Path, g2) -> dict:
    name, fields, seed, warmup, rules, log, steps = spec
    run, twin = _Run(spec, root, True), _Run(spec, root, False)
    world = run.world
    start = world.step_count
    samples = []
    extinctions_before = world.extinctions
    for k in range(steps + 1):
        run.act_due(k)
        twin.act_due(k)
        if k % SAMPLE_EVERY == 0 or k == steps:
            h = g2.state_hash(world)
            assert h == g2.state_hash(twin.world), f"{name}: tracking changed the history at step {world.step_count}"
            samples.append({"step": world.step_count, "hash": h, "population": len(world.cells),
                            "tracker": tracker_digest(world.tracker), "cells": cells_digest(world),
                            "tiles": hashlib.sha256(tile_words(world)).hexdigest()})
        if k < steps:
            run.step()
            twin.step()
    t = world.tracker
    return {"name": name, "config": None if fields is None else Config(**fields).to_dict(),
            "seed": str(seed), "save": START_SAVE if fields is None else None, "warmup": warmup,
            "rules": None if rules is None else _rules_dict(rules), "actions": [list(a) for a in log],
            "start_step": start, "steps": steps, "samples": samples, "tracker": tracker_dump(t, g2),
            "cells": [[c.id, c.species] for c in sorted(world.cells, key=lambda c: c.id)],
            "facts": {"killed_by_action": run.killed_by_action,
                      "reseeds": world.extinctions - extinctions_before}}


def _rules_dict(rules):
    return _sibling("g3_game_vectors").rules_dict(rules)


def _sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_not_vacuous(cases: list) -> None:
    """The verdict's conditions (ADR-0018), across the cases: every tracker event happens at least once."""
    def total(key):
        return sum(c["tracker"][key] for c in cases)

    rows = [row for c in cases for row in c["tracker"]["species"]]
    assert total("speciations") > 0, "no speciation"
    assert total("novelty") > 0, "no established speciation-born species"
    assert total("pruned") > 0, "no species pruned"
    assert any(row[5] is not None for row in rows), "no retained extinct species"
    assert any(row[2] == ORIGIN_IMMIGRANT for row in rows), "no immigrant root"
    assert any(c["facts"]["killed_by_action"] > 0 for c in cases), "no species driven extinct by an intervention"
    assert any(c["facts"]["reseeds"] > 0 for c in cases), "no reseed after extinction"
    reseed = next(c for c in cases if c["name"] == "created_reseed")
    assert any(row[2] == ORIGIN_SEED and row[4] > 0 for row in reseed["tracker"]["species"]), \
        "the reseed founded no species after step 0"
    for c in cases:
        assert len({s["tracker"] for s in c["samples"]}) > 1, f"{c['name']}: the tracker never changed"


def build(root: Path) -> dict:
    g2 = _golden_module()
    write_start_save(root)
    cases = [run_case(spec, root, g2) for spec in case_specs()]
    check_not_vacuous(cases)
    return {"system": platform.system(), "python": platform.python_version(), "sample_every": SAMPLE_EVERY,
            "origins": list(ORIGINS), "start_save": START_SAVE, "cases": cases}


def write(root: Path, out: Path) -> None:
    doc = build(root)
    out.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{out}: {len(doc['cases'])} species cases")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=GOLDEN, help="golden root; the tracked start save is written there")
    ap.add_argument("--out", type=Path, default=GOLDEN / "species.json")
    args = ap.parse_args(argv)
    write(args.root, args.out)


if __name__ == "__main__":
    main()
