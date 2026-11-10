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


# ------------------------------------------------- hardening (security review, 2026-11-10)
def _saved(seed=5):
    world = World(small_config(), seed=seed)
    for _ in range(10):
        world.step()
    return world_to_dict(world)


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["config"].update(width=10**9), "invalid config"),
    (lambda d: d["config"].update(photo_gain=float("nan")), "invalid config"),
    (lambda d: d["config"].update(width="wide"), "invalid config"),
    (lambda d: d["counters"].update(births=-1), "counter"),
    (lambda d: d["cells"][0][5].__setitem__(0, 7.0), "invalid cell"),
    (lambda d: d["cells"][0].__setitem__(3, float("inf")), "invalid cell"),
    (lambda d: d["organic"][0].__setitem__(0, -1.0), "organic"),
])
def test_load_rejects_hostile_values(mutate, message):
    d = _saved()
    mutate(d)
    with pytest.raises(SaveFormatError, match=message):
        world_from_dict(d)


def test_load_ignores_unknown_counters():
    d = _saved()
    d["counters"]["rng"] = "pwned"
    world = world_from_dict(d)
    assert not isinstance(world.rng, str)


def test_load_rejects_bad_terrain_values():
    d = _saved()
    flat = d["organic"]
    for terrain, message in [
        ({"rock": [[300] * len(flat[0])] * len(flat), "chem": flat, "sun": [1.0] * len(flat[0])}, "0 and 1"),
        ({"rock": [[0] * len(flat[0])] * len(flat), "chem": flat, "sun": [-1.0] * len(flat[0])}, "sun"),
    ]:
        with pytest.raises(SaveFormatError, match=message):
            world_from_dict({**d, "terrain": terrain})


def test_load_caps_decompressed_size_and_rejects_junk(tmp_path, monkeypatch):
    from worldsim import persistence
    path = tmp_path / "w.json.gz"
    save_world(World(small_config(), seed=1), path)
    monkeypatch.setattr(persistence, "MAX_SAVE_BYTES", 100)
    with pytest.raises(SaveFormatError, match="decompresses"):
        load_world(path)
    junk = tmp_path / "junk.json.gz"
    with gzip.open(junk, "wb") as f:
        f.write(b"{not json")
    monkeypatch.setattr(persistence, "MAX_SAVE_BYTES", 10**6)
    with pytest.raises(SaveFormatError, match="not a valid save"):
        load_world(junk)


def test_rejects_a_tracker_that_does_not_match_the_cells():
    d = world_to_dict(World(small_config(), seed=1))
    short = json.loads(json.dumps(d))
    short["tracker"]["species"][0][3] = short["tracker"]["species"][0][3][:10]   # founder from an older genome
    with pytest.raises(SaveFormatError, match="founder"):
        world_from_dict(short)
    orphan = json.loads(json.dumps(d))
    orphan["cells"][0][7] = 987654                                                # species the tracker never saw
    with pytest.raises(SaveFormatError, match="species"):
        world_from_dict(orphan)
