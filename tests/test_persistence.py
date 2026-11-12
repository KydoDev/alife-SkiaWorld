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


MAX_COUNT = 1 << 62     # the Rust loader's bound (engine-rs/src/save.rs MAX_COUNT)


def _set_cell(field, value):
    def mutate(d):
        d["cells"][0][field] = value
    return mutate


@pytest.mark.parametrize("value", [MAX_COUNT + 1, -1, 1.5, True, "7"])
@pytest.mark.parametrize("mutate, message", [
    (lambda v: _set_cell(0, v), "cell id"),
    (lambda v: _set_cell(4, v), "age"),
    (lambda v: _set_cell(6, v), "lineage"),
    (lambda v: lambda d: d.update(step_count=v), "step_count"),
    (lambda v: lambda d: d.update(next_id=v), "next_id"),
    (lambda v: lambda d: d["counters"].update(births=v), "counter"),
])
def test_load_bounds_ids_ages_lineages_and_counters_like_the_kernel(mutate, message, value):
    """Integers the kernel hashes as u64 must be in 0..=2^62 in both loaders, so the two accept the same saves."""
    d = _saved()
    mutate(value)(d)
    with pytest.raises(SaveFormatError, match=message):
        world_from_dict(d)


def test_load_accepts_the_largest_bound_values():
    d = _saved()
    d["cells"][0][4] = d["cells"][0][6] = MAX_COUNT
    d["step_count"] = d["next_id"] = MAX_COUNT
    world = world_from_dict(d)
    assert world.next_id == MAX_COUNT and world.cells[0].lineage == MAX_COUNT


def test_load_accepts_a_next_id_equal_to_the_newest_cell_id():
    """`new_id` pre-increments, so `next_id` is the last id handed out: equal is the normal case."""
    d = _saved()
    d["next_id"] = max(row[0] for row in d["cells"])
    world_from_dict(d)


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["cells"][0].__setitem__(1, True), "outside the grid"),
    (lambda d: d["cells"][0].__setitem__(2, 1.0), "outside the grid"),
    (lambda d: next(r for r in d["cells"] if r[8])[8].__setitem__(0, 1.0 * next(r for r in d["cells"] if r[8])[8][0]),
     "bonded to missing"),
    (lambda d: d["tracker"].update(next_id=1), "tracker next_id"),
    (lambda d: d["tracker"].update(novelty=-1), "tracker novelty"),
    (lambda d: d.update(step_count="x" * 100_000), "step_count"),
])
def test_load_wants_json_integers_for_tiles_bonds_and_the_tracker(mutate, message):
    d = _saved()
    mutate(d)
    with pytest.raises(SaveFormatError, match=message) as e:
        world_from_dict(d)
    assert len(str(e.value)) < 200, "the message must not echo a huge hostile value"


def test_load_rejects_a_next_id_below_a_cell_id():
    """The next birth would reuse a living cell's id."""
    d = _saved()
    d["next_id"] = max(row[0] for row in d["cells"]) - 1
    with pytest.raises(SaveFormatError, match="next_id"):
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
