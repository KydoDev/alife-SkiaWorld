"""scripts/g3_game_vectors.py (G3 P7, ADR-0017): the game golden file is what play.py gives, its cases are not
vacuous, an idle game leaves the world's own golden hashes, and the kernel's distance rule equals math.hypot."""
import csv
import importlib.util
import json
import math
import platform
from pathlib import Path

import pytest

from worldsim.play import MILESTONES, TOOLS, GameRules

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "engine-rs" / "tests" / "golden"


def _module():
    spec = importlib.util.spec_from_file_location("g3_game_vectors", ROOT / "scripts" / "g3_game_vectors.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def committed():
    return json.loads((GOLDEN / "games.json").read_text(encoding="utf-8"))


def _off_os(request, committed):
    if platform.system() != committed["system"]:
        request.applymarker(pytest.mark.xfail(strict=False, reason=f"made on {committed['system']}; libm may differ"))


def test_defaults_tools_and_milestones_are_plays(committed):
    """Not stepped: equal on every OS. The kernel's default rules are checked against this record."""
    gv = _module()
    assert committed["default_rules"] == gv.rules_dict(GameRules())
    assert committed["tools"] == list(TOOLS)
    assert committed["milestones"] == list(MILESTONES)


def test_committed_game_vectors_match_this_python(request, committed):
    _off_os(request, committed)
    assert committed["cases"] == _module().build(GOLDEN)["cases"], "regenerate games.json"


def test_an_idle_game_leaves_the_worlds_golden_hashes(request, committed):
    """The game draws nothing from the RNG and never changes the simulation (ADR-0017 Decision 3)."""
    _off_os(request, committed)
    for case in (c for c in committed["cases"] if c["name"].startswith("idle")):
        lines = (GOLDEN / case["set"] / "hashes.csv").read_text(encoding="utf-8").splitlines()
        golden = {int(r["step"]): r["hash"] for r in csv.DictReader(lines)}
        assert len(case["hashes"]) > 5
        for step, digest in case["hashes"]:
            assert golden[step] == digest, f"{case['name']} at step {step}"


def test_the_generator_refuses_vacuous_cases():
    gv = _module()
    idle = {"name": "idle_x", "achieved": {"giant": 225}, "actions": []}
    with pytest.raises(AssertionError, match="idle player"):
        gv.check_not_vacuous(idle, set())
    with pytest.raises(AssertionError, match="expected"):
        gv.check_not_vacuous({"name": "abyss", "achieved": {}, "actions": []}, {"abyss"})
    free = {"name": "budget", "achieved": {}, "actions": [
        {"tool": "meteorite", "accepted": True, "budget": "a"},
        {"tool": "volcano", "accepted": False, "budget": "a"},
        {"tool": "mountain", "accepted": True, "budget": "a"},
        {"tool": "mountain", "accepted": False, "budget": "b"},     # charged although refused
        {"tool": "nutrients", "accepted": True, "budget": "c"}]}
    with pytest.raises(AssertionError, match="free"):
        gv.check_not_vacuous(free, set())
    collapsed = {"name": "strike_window", "achieved": {}, "actions": [], "trace": [{"collapse": "00"}]}
    with pytest.raises(AssertionError, match="window"):
        gv.check_not_vacuous(collapsed, set())


def test_integer_distance_rule_equals_math_hypot():
    """ADR-0017 Decision 5: the kernel uses sqrt of the exact integer sum, Python math.hypot; equal bit for bit."""
    for dx in range(0, 1001):
        for dy in range(0, 1001, 7):
            assert math.hypot(dx, dy) == math.sqrt(dx * dx + dy * dy), (dx, dy)
