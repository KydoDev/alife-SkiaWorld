"""F2 living environment: light cycles, terrain, vents."""
import math
import random

import numpy as np
import pytest

from worldsim import Config, World
from worldsim.persistence import SaveFormatError, load_world, save_world, world_from_dict, world_to_dict
from worldsim.terrain import Terrain, generate_terrain
from worldsim.world import G_CHEMO, G_DIV, Cell


def cycle_config(**kw):
    base = dict(width=40, height=20, initial_cells=80, day_length=50, day_amplitude=1.0,
                year_length=300, season_amplitude=0.5)
    base.update(kw)
    return Config(**base)


def state(world):
    return ([(c.id, c.x, c.y, c.energy, c.age, tuple(c.genes), tuple(b.id for b in c.bonds))
             for c in world.cells], world.organic.tobytes(), world.stats())


def test_constant_light_by_default():
    world = World(Config(width=40, height=20, initial_cells=80), seed=1)
    assert all(world.light_factor(t) == 1.0 for t in range(0, 1000, 7))


def test_light_cycle_is_mean_preserving_and_reaches_darkness():
    world = World(cycle_config(season_amplitude=0.0), seed=1)
    factors = [world.light_factor(t) for t in range(50)]
    assert math.isclose(sum(factors) / len(factors), 1.0, abs_tol=1e-9)
    assert min(factors) < 0.01 and max(factors) > 1.99


def test_seasons_modulate_daily_light():
    world = World(cycle_config(day_amplitude=0.0), seed=1)
    assert math.isclose(world.light_factor(75), 1.5)    # summer peak (quarter year)
    assert math.isclose(world.light_factor(225), 0.5)   # winter trough


def test_light_field_follows_the_factor():
    world = World(cycle_config(season_amplitude=0.0), seed=1)
    world.now = 37                                      # deep night
    world.update_light()
    night = world.light.max()
    world.now = 12                                      # near noon
    world.update_light()
    assert night < 0.05 * world.light.max()


def test_resume_mid_cycle_matches_uninterrupted_run(tmp_path):
    total, split = 240, 113                             # split inside a day and a season
    straight = World(cycle_config(), seed=4)
    for _ in range(total):
        straight.step()
    first = World(cycle_config(), seed=4)
    for _ in range(split):
        first.step()
    save_world(first, tmp_path / "w.json.gz")
    resumed = load_world(tmp_path / "w.json.gz")
    for _ in range(total - split):
        resumed.step()
    assert state(resumed) == state(straight)


@pytest.mark.parametrize("seed", [2, 9])
def test_cycles_are_deterministic(seed):
    a, b = World(cycle_config(), seed=seed), World(cycle_config(), seed=seed)
    for _ in range(150):
        a.step()
        b.step()
    assert state(a) == state(b)


# ------------------------------------------------------------------ terrain and vents
def terrain_config(**kw):
    base = dict(width=40, height=24, initial_cells=150, rock_fraction=0.25, vent_count=3,
                move_upkeep=0.0, immigration_rate=2.0)
    base.update(kw)
    return Config(**base)


def test_default_terrain_is_flat():
    t = generate_terrain(Config(width=30, height=10), seed=3)
    assert t.is_flat and t.rock.shape == (10, 30)


def test_terrain_is_seeded_and_independent_of_world_rng():
    cfg = terrain_config()
    a, b = generate_terrain(cfg, 5), generate_terrain(cfg, 5)
    assert np.array_equal(a.rock, b.rock) and np.array_equal(a.chem, b.chem)
    assert not np.array_equal(a.rock, generate_terrain(cfg, 6).rock)
    world = World(cfg, seed=5, populate=False)
    assert world.rng.getstate() == random.Random(5).getstate()
    assert 0.15 < world.terrain.rock.mean() < 0.35
    assert not world.terrain.rock[0].any()                  # surface row is always water


def test_cells_never_occupy_rock():
    world = World(terrain_config(), seed=2)
    rock = world.terrain.rock
    for _ in range(200):
        world.step()
        assert not any(rock[c.y, c.x] for c in world.cells)
    assert world.births > 0


def test_rocks_cast_shadow_and_hold_organic():
    world = World(terrain_config(), seed=2)
    rock = world.terrain.rock
    below = np.cumsum(rock, axis=0) > 0
    for _ in range(100):
        world.step()
    assert np.all(world.light[below] == 0.0)
    assert np.all(world.chem[rock] == 0.0)
    assert world.chem.max() > 0.5


def test_chemosynthesis_feeds_cells_at_vents():
    cfg = terrain_config(initial_cells=0, immigration_rate=0.0, base_cost=0.0, pred_upkeep=0.0)
    world = World(cfg, seed=2)
    y, x = np.unravel_index(np.argmax(world.chem), world.chem.shape)
    genes = [0.0] * 10
    genes[G_CHEMO] = 1.0
    genes[G_DIV] = 1.0                                        # high division threshold: just eat
    cell = Cell(world._new_id(), int(x), int(y), 10.0, genes, 1, cfg)
    world._place(cell)
    world.step()
    assert cell.energy == pytest.approx(10.0 + cfg.chemo_gain * world.chem[y, x])


def test_terrain_resume_matches_uninterrupted_run(tmp_path):
    cfg = terrain_config(day_amplitude=0.8, day_length=40)
    straight = World(cfg, seed=8)
    for _ in range(160):
        straight.step()
    first = World(cfg, seed=8)
    for _ in range(70):
        first.step()
    save_world(first, tmp_path / "t.json.gz")
    resumed = load_world(tmp_path / "t.json.gz")
    assert np.array_equal(resumed.terrain.rock, first.terrain.rock)
    for _ in range(90):
        resumed.step()
    assert state(resumed) == state(straight)


def test_custom_terrain_survives_save_without_regeneration():
    cfg = Config(width=20, height=10, initial_cells=20)
    t = Terrain.flat(20, 10)
    t.rock[8:, :5] = True
    t.sun[:] = np.linspace(0.5, 1.5, 20)
    t.chem[7, 2] = 2.0
    world = World(cfg, seed=1, terrain=t)
    copy = world_from_dict(world_to_dict(world))           # cfg alone would regenerate a flat world
    assert np.array_equal(copy.terrain.rock, t.rock) and np.array_equal(copy.terrain.sun, t.sun)
    assert np.array_equal(copy.base_light, world.base_light)


def test_load_rejects_bad_terrain_and_cells_on_rock():
    world = World(terrain_config(), seed=2)
    d = world_to_dict(world)
    bad = {**d, "terrain": {**d["terrain"], "sun": [1.0]}}
    with pytest.raises(SaveFormatError):
        world_from_dict(bad)
    with pytest.raises(SaveFormatError):
        world_from_dict({**d, "terrain": {"rock": "x"}})
    ry, rx = np.argwhere(world.terrain.rock)[0]
    on_rock = {**d, "cells": [[*d["cells"][0][:1], int(rx), int(ry), *d["cells"][0][3:]]]}
    on_rock["cells"][0][8] = []
    with pytest.raises(SaveFormatError, match="rock"):
        world_from_dict(on_rock)


def test_world_rejects_mismatched_terrain():
    with pytest.raises(ValueError):
        World(Config(width=20, height=10), seed=1, terrain=Terrain.flat(10, 10))


def test_light_transcendentals_come_from_libm():
    """G2 regression: depth attenuation and shade ** (cells above) must equal math.exp / math.pow bit for bit.
    numpy's np.exp / np.power take SIMD paths on AVX-512 CPUs that differ from libm (and from the Rust kernel)
    by an ULP at some rows (seen on the Linux CI runner: exp at row 36, pow at k = 4, 10, 31, 33)."""
    import math

    from worldsim.world import Cell

    cfg = Config(width=4, height=64, initial_cells=0)
    w = World(cfg, seed=1, track_species=False, populate=False)
    for y in range(cfg.height):                       # a full column: every count of cells above occurs
        cid = w._new_id()
        w._place(Cell(cid, 0, y, 40.0, w.random_genes(), cid, cfg))
    w.update_light()
    for y in range(cfg.height):
        depth = cfg.light_max * math.exp(-float(y) / cfg.light_depth)
        assert w.base_light[y, 1] == depth
        assert w.light[y, 0] == depth * math.pow(cfg.shade, float(y))
        assert w.light[y, 1] == depth
