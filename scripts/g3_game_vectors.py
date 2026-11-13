"""G3 P7 golden vectors of the game rules (ADR-0017), from Python's reference `worldsim/play.py`.

Each case starts from a golden start save, attaches a `play.Game` with its rules, applies a G1 action log (step offset
from the save, tool, x, y) when the world reaches that step, `play.replay`'s timing, and records per action whether
it happened and the budget after it, the milestones reached and their steps, the state hash every HASH_EVERY steps
and at the end, and the final budget. At every milestone check it also records what the check measures (the trace:
chemosynthesizers near player vents, specialists per strategy, the largest colony, cells per sea, the smoothed
population and the cataclysm state), so a port that differs below a threshold still fails. Floats are IEEE-754 bit
patterns (hex). The generator asserts the verdict's non-vacuous conditions in Python (each milestone case reaches its
milestones, idle cases reach none, the budget case refuses for budget and refuses a mountain on rock for free, strikes
spread past the window never collapse), so a golden file can never pass vacuously.

Stepped values depend on libm (`volcanic` steps through sin): like the other golden files it is regenerated per
platform; `scripts/g2_golden.py --all` writes it too. On its own:

    python scripts/g3_game_vectors.py --root engine-rs/tests/golden --out engine-rs/tests/golden/games.json
"""
import argparse
import dataclasses
import importlib.util
import json
import platform
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from worldsim.persistence import load_world  # noqa: E402
from worldsim.play import MILESTONES, SPECIALIST, TOOLS, Game, GameRules, colony_sizes, seas  # noqa: E402

GOLDEN = ROOT / "engine-rs/tests/golden"
HASH_EVERY = 100
_BIG = dict(budget_start=1e6, budget_max=1e6)      # milestone cases: the budget is not what they test


def _walls():
    """Two full-depth mountain walls (x is toroidal): two seas."""
    return [(0, "mountain", x, y) for x in (20, 100) for y in range(0, 64, 2)]


def _strike_rows(plan):
    """A row of eight meteorites (radius 10) at depth y for each (offset, y)."""
    return [(offset, "meteorite", x, y) for offset, y in plan for x in range(0, 160, 20)]


def case_specs():
    """(name, set, rules, log, steps, expected milestones). Lowered thresholds keep the runs short, as
    tests/test_play.py does; `GameRules()` where the case is about the defaults."""
    budget_log = [
        (0, "volcano", 40, 30),        # 100 -> 60
        (0, "meteorite", 120, 10),     # 60 -> 40: accepted whatever it hits
        (0, "nutrients", 10, 10),      # 40 -> 30
        (0, "nutrients", 30, 10),      # 30 -> 20
        (0, "mountain", 60, 20),       # 20 -> 16
        (0, "mountain", 60, 20),       # all rock already: refused, free
        (1, "volcano", 70, 30),        # 16 < 40: refused for budget
        (1, "meteorite", 5, 5),        # 16 < 20: refused for budget
        (90, "meteorite", 5, 5),       # 16 + 90 * 0.05 = 20.5 >= 20: accepted
    ]
    return [
        ("idle_default", "default", GameRules(), [], 1000, set()),
        ("idle_volcanic", "volcanic", GameRules(), [], 1000, set()),
        ("budget", "default", GameRules(), budget_log, 120, set()),
        ("abyss_balance_giant", "default", GameRules(abyss_cells=1, balance_cells=1, giant_colony=12, **_BIG),
         [(0, "volcano", x, 62) for x in range(5, 160, 15)], 600, {"abyss", "balance", "giant"}),
        ("plastic_abyss_giant", "plasticity", GameRules(abyss_cells=3, balance_cells=2, giant_colony=12, **_BIG),
         [(0, "volcano", 80, 62), (0, "volcano", 30, 62)], 400, {"abyss", "giant"}),
        ("survivor", "default", GameRules(collapse_window=50, **_BIG),
         [(30, "meteorite", x, y) for x in range(0, 160, 20) for y in (8, 30, 52)], 900, {"survivor"}),
        # strikes spread past the 20-step window: no single record kills a third of life, though all of them
        # together do (76 of 225); the last two batches share one record (the window's accumulation)
        ("strike_window", "default", GameRules(collapse_window=20, **_BIG),
         _strike_rows([(0, 30), (30, 30), (60, 30), (70, 52), (70, 30)]), 120, set()),
        ("divided", "default", GameRules(divided_cells=20, **_BIG), _walls(), 50, {"divided"}),
    ]


def _golden_module():
    spec = importlib.util.spec_from_file_location("g2_golden", ROOT / "scripts/g2_golden.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rules_dict(rules: GameRules) -> dict:
    """The rules as the kernel's `WsGameRules` lays them out: per-tool values as lists in `TOOLS` order."""
    d = dataclasses.asdict(rules)
    d["cost"] = [float(rules.cost[t]) for t in TOOLS]
    d["radius"] = [int(rules.radius[t]) for t in TOOLS]
    return d


def measures(game, g2) -> dict:
    """What `Game.check_milestones` measures, whatever has been reached already (the kernel's `Game::measures`)."""
    w = game.world
    cells = w.cells
    per_sea = []
    if w.has_rock:
        labels, n = seas(w)
        per_sea = np.bincount([labels[c.y, c.x] for c in cells], minlength=n).tolist() if n else []
    collapse = game._collapsed_from
    return {"step": w.step_count,
            "near": game._chemo_near_player_vents(),
            "specialists": [sum(1 for c in cells if getattr(c, a) >= SPECIALIST) for a in ("photo", "sapro", "pred")],
            "colony": max(colony_sizes(cells), default=0),
            "seas": per_sea,
            "smoothed": g2.f64_hex(float(game._smoothed())),
            "collapse": None if collapse is None else g2.f64_hex(float(collapse)),
            "dipped": bool(game._strike and game._strike["dipped"])}


def run_case(name, set_name, rules, log, steps, root: Path, g2) -> dict:
    world = load_world(root / set_name / "start.json.gz")
    game = Game(world, rules)
    start = world.step_count
    pending = sorted(log, key=lambda a: a[0])          # stable: same-offset order kept
    actions, hashes, trace, i = [], [], [], 0
    for k in range(steps + 1):
        while i < len(pending) and pending[i][0] <= k:
            offset, tool, x, y = pending[i]
            accepted = game.act(tool, x, y)
            actions.append({"offset": offset, "tool": tool, "x": x, "y": y, "accepted": accepted,
                            "budget": g2.f64_hex(game.budget)})
            i += 1
        if k % HASH_EVERY == 0 or k == steps:
            hashes.append([world.step_count, g2.state_hash(game.world)])
        if k < steps:
            game.step()
            if world.step_count % rules.check_every == 0:
                trace.append(measures(game, g2))
    assert i == len(pending), f"{name}: actions after the last step"
    return {"name": name, "set": set_name, "rules": rules_dict(rules), "steps": steps, "start_step": start,
            "actions": actions, "achieved": {k: game.achieved[k] for k in MILESTONES if k in game.achieved},
            "budget": g2.f64_hex(game.budget), "player_vents": len(set(game.player_vents)), "hashes": hashes,
            "trace": trace}


def check_not_vacuous(case: dict, expected: set) -> None:
    """The verdict's conditions (ADR-0017): a case that cannot fail is not a test."""
    name, reached = case["name"], set(case["achieved"])
    assert expected <= reached, f"{name}: expected {sorted(expected)}, reached {sorted(reached)}"
    if name.startswith("idle"):
        assert not reached, f"{name}: an idle player reached {sorted(reached)}"
        assert not case["actions"]
    if name == "strike_window":
        assert all(t["collapse"] is None for t in case["trace"]), "strikes outside the window must not add up"
    if name == "budget":
        acts = case["actions"]
        assert any(a["tool"] == "meteorite" and a["accepted"] for a in acts)
        refused = [a for a in acts if not a["accepted"]]
        assert any(a["tool"] in ("volcano", "meteorite") for a in refused), "nothing refused for budget"
        rock = [j for j, a in enumerate(acts) if a["tool"] == "mountain" and not a["accepted"]]
        assert rock and acts[rock[0]]["budget"] == acts[rock[0] - 1]["budget"], "a mountain on rock must be free"
        assert acts[-1]["accepted"], "the budget regenerates"


def build(root: Path) -> dict:
    g2 = _golden_module()
    cases = []
    for name, set_name, rules, log, steps, expected in case_specs():
        case = run_case(name, set_name, rules, log, steps, root, g2)
        check_not_vacuous(case, expected)
        cases.append(case)
    return {"system": platform.system(), "python": platform.python_version(), "tools": list(TOOLS),
            "milestones": list(MILESTONES), "default_rules": rules_dict(GameRules()), "cases": cases}


def write(root: Path, out: Path) -> None:
    doc = build(root)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"{out}: {len(doc['cases'])} game cases")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=GOLDEN, help="golden root holding the start saves")
    ap.add_argument("--out", type=Path, default=GOLDEN / "games.json")
    args = ap.parse_args(argv)
    write(args.root, args.out)


if __name__ == "__main__":
    main()
