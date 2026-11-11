"""The G2 golden vectors (engine-rs/tests/golden/) still describe the Python reference engine.

The portable parts (integer RNG paths, random(), and the state hash of a loaded save) are checked on every
platform. Stepping uses gauss/pow/sin from the platform's maths library, so it is compared only on the OS
the golden files were made on (see ADR-0008, "Determinism and cross-engine verification").
"""
import csv
import importlib.util
import json
import platform
import random
import re
from pathlib import Path

import pytest

from worldsim.persistence import load_world

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("g2_golden", ROOT / "scripts" / "g2_golden.py")
g2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g2)
GOLDEN_SETS = tuple(g2.SETS)   # the single list of golden sets


def test_golden_set_lists_agree():
    """SETS in the script, the committed directories and the Rust tests' GOLDEN_SETS name the same sets."""
    committed = {d.name for d in (ROOT / "engine-rs" / "tests" / "golden").iterdir() if d.is_dir()}
    assert committed == set(GOLDEN_SETS)
    common = (ROOT / "engine-rs" / "tests" / "common" / "mod.rs").read_text(encoding="utf-8")
    rust = re.search(r"GOLDEN_SETS: \[&str; \d+\] = \[([^\]]*)\]", common)
    assert rust, "GOLDEN_SETS not found in engine-rs/tests/common/mod.rs"
    assert re.findall(r'"([^"]+)"', rust.group(1)) == list(GOLDEN_SETS)


@pytest.mark.parametrize("name", GOLDEN_SETS)
def test_committed_set_matches_its_arguments(name):
    """The committed data was made with the arguments SETS declares (else regenerate with --all)."""
    args = g2.build_parser().parse_args([*g2.SET_COMMON, *g2.SETS[name], "--out", "unused"])
    made = json.loads((ROOT / "engine-rs" / "tests" / "golden" / name / "rng.json").read_text(encoding="utf-8"))
    meta = made["meta"]
    assert made["seed"] == args.seed
    assert (meta["warmup"], meta["steps"]) == (args.warmup, args.steps)
    assert meta["planet"] == (args.planet.as_posix() if args.planet else None)
    assert meta.get("set", []) == args.set


@pytest.fixture(scope="module", params=GOLDEN_SETS)
def golden(request):
    return ROOT / "engine-rs" / "tests" / "golden" / request.param


@pytest.fixture(scope="module")
def rng_golden(golden):
    return json.loads((golden / "rng.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def hashes(golden):
    with open(golden / "hashes.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_loaded_save_hash_matches_golden_start(golden, hashes):
    world = load_world(golden / "start.json.gz")
    assert world.step_count == int(hashes[0]["step"])
    assert g2.state_hash(world) == hashes[0]["hash"]


def test_integer_rng_paths_match_golden(rng_golden):
    fresh = g2.rng_vectors(rng_golden["seed"])
    for key in ("start_state", "random", "randrange", "shuffle_50", "choice_9"):
        assert fresh[key] == rng_golden[key], key


def test_rng_vectors_cover_the_seeded_state(rng_golden):
    rng = random.Random(rng_golden["seed"])
    assert list(rng.getstate()[1]) == rng_golden["start_state"]


def test_state_hash_changes_with_the_state(golden):
    world = load_world(golden / "start.json.gz")
    before = g2.state_hash(world)
    world.cells[0].energy += 1e-12
    assert g2.state_hash(world) != before


def test_stepping_matches_golden_on_the_same_os(request, golden, rng_golden, hashes):
    made_on = rng_golden["meta"]["system"]
    if platform.system() != made_on:
        request.applymarker(pytest.mark.xfail(strict=False, reason=f"golden steps made on {made_on}; maths may differ"))
    assert rng_golden["mixed_gauss_random"] == g2.rng_vectors(rng_golden["seed"])["mixed_gauss_random"]
    world = load_world(golden / "start.json.gz")
    for row in hashes[1:31]:
        world.step()
        got = (world.step_count, g2.state_hash(world))
        assert got == (int(row["step"]), row["hash"]), "regenerate the golden files"


def test_dump_step_writes_the_save_of_that_step(tmp_path):
    g2.main(["--seed", "3", "--warmup", "0", "--steps", "3", "--dump-step", "2", "--out", str(tmp_path)])
    with open(tmp_path / "hashes.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    world = load_world(tmp_path / "step_2.json.gz")
    assert world.step_count == 2
    assert g2.state_hash(world) == rows[2]["hash"]
