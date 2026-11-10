"""Save/load: a resumed run must continue exactly like an uninterrupted one."""
import gzip
import json

import pytest

from worldsim import Config, World
from worldsim.persistence import SaveFormatError, load_world, save_world, world_from_dict, world_to_dict


def small_config():
    return Config(width=40, height=20, initial_cells=80)


def snapshot(world):
    """Everything that defines the state, per cell and in list order."""
    return (
        world.step_count, world.next_id, world.births, world.deaths, world.kills,
        [(c.id, c.x, c.y, c.energy, c.age, tuple(c.genes), c.lineage, c.species,
          tuple(b.id for b in c.bonds)) for c in world.cells],
        world.organic.tobytes(),
        world.stats(),
    )


@pytest.mark.parametrize("split", [60, 170])
def test_resume_from_file_matches_uninterrupted_run(tmp_path, split):
    total = 260
    straight = World(small_config(), seed=21)
    for _ in range(total):
        straight.step()

    first = World(small_config(), seed=21)
    for _ in range(split):
        first.step()
    assert any(c.bonds for c in first.cells), "split point must have colonies to be meaningful"
    path = tmp_path / "world.json.gz"
    save_world(first, path)

    resumed = load_world(path)
    for _ in range(total - split):
        resumed.step()

    assert snapshot(resumed) == snapshot(straight)


def test_roundtrip_preserves_state_exactly():
    world = World(small_config(), seed=5)
    for _ in range(120):
        world.step()
    copy = world_from_dict(json.loads(json.dumps(world_to_dict(world))))
    assert snapshot(copy) == snapshot(world)
    assert copy.rng.getstate() == world.rng.getstate()


def test_world_without_tracker_roundtrips():
    world = World(small_config(), seed=5, track_species=False)
    for _ in range(30):
        world.step()
    copy = world_from_dict(world_to_dict(world))
    assert copy.tracker is None
    assert snapshot(copy) == snapshot(world)


def test_rejects_wrong_format_and_version():
    d = world_to_dict(World(small_config(), seed=1))
    with pytest.raises(SaveFormatError):
        world_from_dict({**d, "format": "something-else"})
    with pytest.raises(SaveFormatError):
        world_from_dict({**d, "version": 999})


def test_rejects_inconsistent_cells():
    d = world_to_dict(World(small_config(), seed=1))
    dup = json.loads(json.dumps(d))
    dup["cells"][1][1:3] = dup["cells"][0][1:3]          # two cells on the same tile
    with pytest.raises(SaveFormatError):
        world_from_dict(dup)
    outside = json.loads(json.dumps(d))
    outside["cells"][0][1] = 10_000
    with pytest.raises(SaveFormatError):
        world_from_dict(outside)
    dangling = json.loads(json.dumps(d))
    dangling["cells"][0][8] = [987654]
    with pytest.raises(SaveFormatError):
        world_from_dict(dangling)


def test_save_file_is_plain_gzip_json(tmp_path):
    path = tmp_path / "w.json.gz"
    save_world(World(small_config(), seed=1), path)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        assert json.load(f)["format"] == "worldsim-save"
