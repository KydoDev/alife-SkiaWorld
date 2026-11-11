"""G2 golden vectors for interventions (ADR-0013 piece 3, Decision 6): the five `play.py` edits applied to
golden start saves, with what the kernel's `World::intervene` must reproduce.

Each case loads ROOT/<set>/start.json.gz (a golden set in the same root, so `g2_golden.py --all ROOT` writes this
file as ROOT/interventions.json after the sets, and CI regenerates it on Linux) and steps it, applying each action
with the `play.py` function of its kind at its step, before the next step, in list order (`play.replay`'s timing).
After each action it records the return value, the state hash, the terrain digest (ADR-0012's, with the live
`World.organic`) and the SHA-256 of `render_rgb`; then one state hash per step. Coordinates that depend on the
save (a bonded cell, the strongest natural vent) are chosen here from the live world and recorded, and the
generator fails when a case would not show what it is meant to (`_check`). Checked by
engine-rs/tests/golden_interventions.rs; `iv_game` is also replayed through `play.replay` by pytest.

An action record is `(step, kind, x, y, radius, amount)`, the arguments of the kernel's `ws_world_intervene`:
kind 1 nutrients (amount = organic per tile), 2 meteorite, 3 raise rock, 4 dig, 5 vent (amount = max_chem,
radius 0); an argument the kind does not use is 0.

    python scripts/g2_intervention_vectors.py --root engine-rs/tests/golden \
        --out engine-rs/tests/golden/interventions.json
"""
import argparse
import functools
import hashlib
import importlib.util
import json
import platform
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from worldsim import play  # noqa: E402
from worldsim.persistence import load_world  # noqa: E402
from worldsim.render import render_rgb  # noqa: E402
from worldsim.terrain import vent_plume  # noqa: E402

NUTRIENTS, METEORITE, RAISE_ROCK, DIG, VENT = 1, 2, 3, 4, 5
# G1 tool name -> kind, for the game log of iv_game
TOOL_KIND = {"nutrients": NUTRIENTS, "meteorite": METEORITE, "mountain": RAISE_ROCK, "dig": DIG, "volcano": VENT}
TAIL = 200                     # steps hashed after the last action
# iv_game: a G1 log (offset from the save's step, tool, x, y), replayed by pytest through play.replay
GAME_LOG = [(0, "nutrients", 40, 10), (0, "volcano", 100, 40), (5, "meteorite", 60, 20), (10, "mountain", 30, 5),
            (10, "mountain", 30, 5), (15, "dig", 30, 5), (20, "volcano", 30, 5), (20, "nutrients", 159, 63)]


@functools.cache
def _golden():
    spec = importlib.util.spec_from_file_location("g2_golden", Path(__file__).with_name("g2_golden.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply(world, kind, x, y, radius, amount):
    """One edit through its `play.py` function (the reference of record); returns its value."""
    if kind == NUTRIENTS:
        return play.add_nutrients(world, x, y, radius, amount)
    if kind == METEORITE:
        return play.meteorite(world, x, y, radius)
    if kind == RAISE_ROCK:
        return play.raise_rock(world, x, y, radius)
    if kind == DIG:
        return play.dig(world, x, y, radius)
    if kind == VENT:
        return play.add_vent(world, x, y, amount)
    raise ValueError(f"unknown intervention kind {kind}")


def game_actions(log, rules=None):
    """A G1 log `(step, tool, x, y)` as explicit actions, with the tool parameters of `rules`."""
    rules = rules or play.GameRules()
    out = []
    for step, tool, x, y in log:
        kind = TOOL_KIND[tool]
        radius = 0 if kind == VENT else rules.radius[tool]
        amount = {NUTRIENTS: rules.nutrients_amount, VENT: rules.max_chem}.get(kind, 0.0)
        out.append((step, kind, x, y, radius, amount))
    return out


# ------------------------------------------------------------------ coordinates chosen from the live world
def _bonded_in_reach(world, x, r):
    """y of the first bonded cell (list order) within toroidal distance r of column x: a disc at (x, y, r) hits it.
    Without one, row 0: the case still runs and `_check` says which condition went missing."""
    for c in world.cells:
        dx = abs(c.x - x)
        if c.bonds and min(dx, world.W - dx) <= r:
            return c.y
    return 0


def _strongest_vent(world):
    i = int(np.argmax(world.terrain.chem))
    return i % world.W, i // world.W


def _above_seabed(world):
    """The water tile right above the first rock of the first column that has rock."""
    rock = world.terrain.rock
    x = int(np.flatnonzero(rock.any(axis=0))[0])
    return x, int(np.flatnonzero(rock[:, x])[0]) - 1


def _ridge_top(world):
    """The highest rock tile (smallest y; the first in row-major order)."""
    i = int(np.flatnonzero(world.terrain.rock.ravel())[0])
    return i % world.W, i // world.W


# Each case: (name, golden set, actions). An action is (offset from the save's step, kind, x, y, radius, amount);
# x, y may be a function of the live world returning one value, `at` a function returning (x, y).
def at(f):
    return ("at", f)


def case_specs():
    W, H = 160, 64                 # default and volcanic sizes (asserted at load)
    mid = W // 2
    return [
        ("iv_default", "default", [
            (0, NUTRIENTS, 0, 0, 6, 15.0),                       # wraps left, top row
            (0, NUTRIENTS, 0, 0, 0, 15.0),                       # radius 0: one tile
            (0, METEORITE, W - 1, lambda w: _bonded_in_reach(w, W - 1, 10), 10, 0.0),   # wraps right, bonded kill
            (10, RAISE_ROCK, mid, H - 1, 2, 0.0),                # first rock: has_rock false -> true
            (11, RAISE_ROCK, mid, H - 1, 2, 0.0),                # all rock already: returns 0, light left stale
            (15, VENT, mid + 4, H - 1, 0, 4.0),                  # first vent: has_chem false -> true
            (16, VENT, mid, H - 1, 0, 4.0),                      # on rock: returns 0, light left stale
            (20, DIG, mid, H - 1, 3, 0.0),                       # removes all rock: has_rock true -> false
            (25, RAISE_ROCK, W // 4, 0, 2, 0.0),                 # rock on row 0 shades whole columns
        ]),
        ("iv_volcanic", "volcanic", [
            (0, VENT, at(_strongest_vent), None, 0, 4.0),        # stacking on a natural vent, capped
            (0, VENT, at(_strongest_vent), None, 0, 0.5),        # below the natural value: max keeps it
            (5, RAISE_ROCK, at(_strongest_vent), None, 2, 0.0),  # chem zeroed under rock, the plume kept elsewhere
            (10, NUTRIENTS, at(_above_seabed), None, 3, 15.0),   # disc over the seabed: rock tiles skipped
            (15, DIG, at(_ridge_top), None, 2, 0.0),             # through the ridge
            (20, DIG, 0, 0, 1, 0.0),                             # on water: returns 0, refreshes anyway
        ]),
        ("iv_reseed", "combined_reseed", [
            (0, VENT, 1, 1, 0, 4.0),                             # no natural vents: has_chem false -> true
            (0, RAISE_ROCK, 0, 0, 8, 0.0),                       # r = W + H: every cell crushed, chem gone
            (10, DIG, 0, 0, 8, 0.0),                             # whole world dug: the next step reseeds
        ]),
        ("iv_width2", "combined_width2", [
            (0, METEORITE, 0, lambda w: _bonded_in_reach(w, 0, 1), 1, 0.0),
            (0, METEORITE, 1, lambda w: _bonded_in_reach(w, 1, 2), 2, 0.0),
            (3, VENT, 0, 5, 0, 4.0),
            (3, VENT, 1, 20, 0, 4.0),
        ]),
        ("iv_game", "volcanic", game_actions(GAME_LOG)),
    ], (W, H)


def _resolve(world, x, y):
    if isinstance(x, tuple) and x[0] == "at":
        return x[1](world)
    return (x(world) if callable(x) else x), (y(world) if callable(y) else y)


def _terrain_digest(world):
    t = world.terrain
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(t.rock, dtype=np.uint8).tobytes())
    for a in (t.chem, t.sun, world.organic):
        h.update(np.ascontiguousarray(a, dtype="<f8").tobytes())
    return h.hexdigest()


def _render_digest(world):
    return hashlib.sha256(render_rgb(world).tobytes(order="C")).hexdigest()


def run_case(name, set_name, specs, root: Path) -> dict:
    g = _golden()
    world = load_world(root / set_name / "start.json.gz")
    start = world.step_count
    pending = [(start + k, kind, x, y, r, a) for k, kind, x, y, r, a in specs]
    end = pending[-1][0] + TAIL
    actions, hashes = [], [[world.step_count, len(world.cells), g.state_hash(world)]]
    while True:
        while pending and pending[0][0] == world.step_count:
            step, kind, x, y, r, a = pending.pop(0)
            x, y = _resolve(world, x, y)
            actions.append(_record(world, g, step, kind, int(x), int(y), r, a))
        if world.step_count == end:
            break
        world.step()
        hashes.append([world.step_count, len(world.cells), g.state_hash(world)])
    return {"name": name, "set": set_name, "width": world.W, "height": world.H, "actions": actions,
            "hashes": hashes}


def _record(world, g, step, kind, x, y, r, a) -> dict:
    t = world.terrain
    disc = play._disc(world, x, y, r)
    before = {"population": len(world.cells), "has_rock": bool(world.has_rock), "has_chem": bool(world.has_chem)}
    bonded = sum(1 for c in world.cells if c.bonds and disc[c.y, c.x])
    disc_rock = int((disc & t.rock).sum())                # before the edit: raise_rock changes rock in place
    capped = False
    if kind == VENT and not t.rock[y, x]:
        plume = vent_plume(world.H, world.W, x, y, world.cfg.vent_strength, world.cfg.vent_radius)
        capped = bool(np.any((t.chem > 0) & (t.chem + plume > a)))
    ret = apply(world, kind, x, y, r, a)
    render = _render_digest(world)
    stale_light = False
    if ret == 0 and kind in (RAISE_ROCK, VENT):
        # an early return leaves the light of the last step; show it differs from a fresh update_light
        light = world.light
        world.update_light()
        stale_light = _render_digest(world) != render
        world.light = light
    return {"step": step, "kind": kind, "x": x, "y": y, "radius": r, "amount": a, "ret": int(ret),
            "hash": g.state_hash(world), "terrain": _terrain_digest(world), "render": render,
            "before": before, "population": len(world.cells), "has_rock": bool(world.has_rock),
            "has_chem": bool(world.has_chem), "bonded_in_disc": bonded, "disc_rock": disc_rock,
            "capped_natural": capped, "stale_light": stale_light}


def _check(cases) -> None:
    """The non-vacuous conditions of ADR-0013 Decision 6: fail rather than write a case that proves less."""
    acts = [(c, a) for c in cases for a in c["actions"]]

    def need(cond, what):
        if not any(cond(c, a) for c, a in acts):
            raise SystemExit(f"interventions vectors: no action shows {what}")
    need(lambda c, a: a["kind"] == METEORITE and a["ret"] > 0 and a["bonded_in_disc"] > 0, "a kill of a bonded cell")
    need(lambda c, a: a["kind"] == RAISE_ROCK and a["population"] < a["before"]["population"], "a raise_rock kill")
    for flag in ("has_rock", "has_chem"):
        need(lambda c, a, f=flag: not a["before"][f] and a[f], f"{flag} false -> true")
        need(lambda c, a, f=flag: a["before"][f] and not a[f], f"{flag} true -> false")
    need(lambda c, a: a["x"] == 0 and a["radius"] > 0, "a disc wrapping at x = 0")
    need(lambda c, a: a["x"] == c["width"] - 1 and a["radius"] > 0, "a disc wrapping at x = W-1")
    need(lambda c, a: a["y"] == 0, "row 0")
    need(lambda c, a: a["y"] == c["height"] - 1, "row H-1")
    need(lambda c, a: a["kind"] == VENT and a["capped_natural"], "a capped vent on a natural vent")
    need(lambda c, a: a["kind"] == NUTRIENTS and a["disc_rock"] > 0, "a nutrient disc over rock")
    need(lambda c, a: a["kind"] == RAISE_ROCK and a["ret"] == 0, "raise_rock's no-op return")
    need(lambda c, a: a["kind"] == VENT and a["ret"] == 0, "a vent's no-op return")
    need(lambda c, a: a["kind"] == DIG and a["ret"] == 0, "a dig returning 0")
    for kind, what in ((RAISE_ROCK, "raise_rock"), (VENT, "vent")):
        need(lambda c, a, k=kind: a["kind"] == k and a["stale_light"],
             f"a {what} no-op whose untouched light differs from a fresh one")
    need(lambda c, a: a["before"]["population"] > 0 and a["population"] == 0, "an extinction caused by an edit")


def build(root: Path) -> dict:
    specs, (w, h) = case_specs()
    cases = []
    for name, set_name, actions in specs:
        case = run_case(name, set_name, actions, root)
        if set_name in ("default", "volcanic") and (case["width"], case["height"]) != (w, h):
            raise SystemExit(f"{name}: the {set_name} set is not {w}x{h}; update case_specs")
        cases.append(case)
    _check(cases)
    return {"system": platform.system(), "python": platform.python_version(), "cases": cases}


def write(root: Path, out: Path) -> None:
    doc = build(root)
    out.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{out}: {len(doc['cases'])} intervention cases, {sum(len(c['actions']) for c in doc['cases'])} actions")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, required=True, help="golden root holding the start saves")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    write(args.root, args.out)


if __name__ == "__main__":
    main()
