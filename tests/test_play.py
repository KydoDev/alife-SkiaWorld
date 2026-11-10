"""G1 game rules: interventions keep the engine consistent; milestones and budget."""
import numpy as np
import pytest

from worldsim import Config, World
from worldsim.persistence import load_world, save_world
from worldsim.play import (Game, GameRules, add_vent, colony_sizes, dig, meteorite, raise_rock, replay, seas)


def small(**kw):
    base = dict(width=40, height=20, initial_cells=150)
    base.update(kw)
    return Config(**base)


def consistent(world):
    grid = world.grid
    assert sum(1 for g in grid if g is not None) == len(world.cells)
    for c in world.cells:
        assert c.alive and grid[c.y * world.W + c.x] is c
        assert not world.terrain.rock[c.y, c.x]
        assert all(b.alive and c in b.bonds for b in c.bonds)


def state(world):
    return ([(c.id, c.x, c.y, c.energy, tuple(c.genes), tuple(b.id for b in c.bonds)) for c in world.cells],
            world.organic.tobytes(), world.terrain.rock.tobytes(), world.terrain.chem.tobytes(), world.stats())


def grown(seed=3, steps=40, **kw):
    world = World(small(**kw), seed=seed)
    for _ in range(steps):
        world.step()
    return world


def test_meteorite_kills_the_disc_and_keeps_energy_as_organic():
    world = grown()
    before = len(world.cells)
    organic_before = world.organic.sum()
    killed = meteorite(world, 20, 3, 6)
    assert killed > 0 and len(world.cells) == before - killed
    assert world.organic.sum() > organic_before
    consistent(world)
    for _ in range(20):
        world.step()
    consistent(world)


def test_mountain_crushes_cells_blocks_light_and_dig_reopens():
    world = grown()
    raise_rock(world, 10, 5, 2)
    assert world.terrain.rock[5, 10] and world.has_rock and world.organic[5, 10] == 0.0
    assert np.all(world.light[5:, 10] == 0.0)          # shadow below the new rock, even while paused
    consistent(world)
    for _ in range(30):
        world.step()
    consistent(world)
    dig(world, 10, 5, 2)
    assert not world.terrain.rock[5, 10]
    assert world.base_light[10, 10] > 0


def test_volcano_on_flat_world_feeds_and_is_capped():
    world = grown()
    assert not world.has_chem
    assert add_vent(world, 20, 15, max_chem=4.0) == 1
    assert world.has_chem and world.chem[15, 20] == pytest.approx(world.cfg.vent_strength)
    for _ in range(5):
        add_vent(world, 20, 15, max_chem=4.0)
    assert world.chem.max() <= 4.0
    raise_rock(world, 5, 15, 1)
    assert add_vent(world, 5, 15, max_chem=4.0) == 0    # no vent inside rock


@pytest.mark.parametrize("tool, x, y", [("nutrients", 20, 10), ("meteorite", 20, 4), ("mountain", 12, 8),
                                        ("dig", 12, 8), ("volcano", 30, 17)])
def test_resume_right_after_an_intervention_is_bit_exact(tmp_path, tool, x, y):
    def play(game):
        if tool == "dig":
            game.act("mountain", x, y)
        game.act(tool, x, y)

    straight = Game(grown(seed=6, steps=30))
    play(straight)
    first = Game(grown(seed=6, steps=30))
    play(first)
    save_world(first.world, tmp_path / "g.json.gz")
    resumed = load_world(tmp_path / "g.json.gz")
    for _ in range(40):
        straight.world.step()
        resumed.step()
    assert state(resumed) == state(straight.world)


def test_replaying_the_action_log_reproduces_the_game():
    actions = [(5, "nutrients", 20, 10), (12, "meteorite", 8, 3), (12, "volcano", 30, 18), (20, "mountain", 15, 9)]
    a = replay(World(small(), seed=4), actions, 60)
    b = replay(World(small(), seed=4), actions, 60)
    assert a.actions == b.actions == actions
    assert state(a.world) == state(b.world)


def test_budget_costs_regenerates_and_refuses():
    game = Game(World(small(), seed=1), GameRules(budget_start=45.0, regen=1.0))
    assert game.act("volcano", 20, 15)                  # 45 - 40
    assert not game.act("meteorite", 20, 5)             # 5 < 25: refused, nothing happens
    assert game.actions == [(0, "volcano", 20, 15)]
    for _ in range(20):
        game.step()
    assert game.budget == pytest.approx(25.0)
    assert game.act("meteorite", 20, 5)
    assert not game.act("nutrients", 999, 5)            # outside the world
    with pytest.raises(ValueError):
        game.act("lightning", 1, 1)


def test_no_milestone_without_the_player():
    game = Game(World(small(rock_fraction=0.2, vent_count=2), seed=2))
    for _ in range(300):
        game.step()
    assert game.achieved == {}


def test_divided_ocean_milestone():
    rules = GameRules(divided_cells=20, budget_start=1e6, budget_max=1e6)
    game = Game(World(small(initial_cells=300), seed=5), rules)
    for x in (5, 25):                                    # two full-depth walls (x is toroidal)
        for y in range(0, 20, 2):
            game.act("mountain", x, y)
    assert seas(game.world)[1] == 2
    for _ in range(rules.check_every):
        game.step()
    assert "divided" in game.achieved and game.news


def test_abyss_balance_giant_and_survivor_milestones():
    rules = GameRules(abyss_cells=1, balance_cells=1, giant_colony=2, budget_start=1e6, budget_max=1e6,
                      collapse_window=50)
    game = Game(World(small(initial_cells=400), seed=8), rules)
    game.act("volcano", 20, 18)
    for _ in range(400):
        game.step()
    assert {"abyss", "balance", "giant"} <= set(game.achieved)
    assert "survivor" not in game.achieved
    for x in range(0, 40, 10):
        for y in (2, 10):
            game.act("meteorite", x, y)                  # wipe most life out, not all
    for _ in range(1500):
        game.step()
        if "survivor" in game.achieved:
            break
    assert "survivor" in game.achieved


def test_colony_sizes_and_restart():
    world = grown(steps=80)
    sizes = colony_sizes(world.cells)
    assert sum(sizes) == sum(1 for c in world.cells if c.bonds)
    game = Game(world)
    game.act("mountain", 10, 10)
    game.restart(seed=9)
    assert not game.world.terrain.rock.any() and game.world.seed == 9


def test_total_extinction_is_not_survival():
    rules = GameRules(budget_start=1e6, budget_max=1e6, collapse_window=50)
    game = Game(World(small(), seed=8), rules)
    for _ in range(30):
        game.step()
    for x in range(0, 40, 8):
        for y in range(0, 20, 8):
            game.act("meteorite", x, y)                  # nothing left: the engine reseeds
    assert not game.world.cells
    for _ in range(600):
        game.step()
    assert game.world.extinctions == 1 and "survivor" not in game.achieved


# ------------------------------------------------- regressions (G1 review, 2026-11-10)
def test_survivor_needs_a_real_dip_before_recovery():
    rules = GameRules(budget_start=1e6, budget_max=1e6, kill_fraction=0.01)
    game = Game(World(small(initial_cells=300), seed=8), rules)
    for _ in range(30):
        game.step()
    game.act("meteorite", 20, 3)                         # kills >= 1%, but the population never dips below
    game._smooth.extend([10**6] * 5)                     # a lagging average far above the pre-strike level
    game.step()
    assert "survivor" not in game.achieved


def test_mountain_on_rock_is_free_and_vents_never_weaken():
    game = Game(World(small(), seed=1), GameRules(budget_start=100.0))
    assert game.act("mountain", 10, 10)
    budget = game.budget
    assert not game.act("mountain", 10, 10) and game.budget == budget
    w = game.world
    w.terrain.chem[5, 30] = 9.0                          # e.g. an image planet with a rich spot
    w.set_terrain(w.terrain)
    game.act("volcano", 5, 15)
    assert w.chem[5, 30] == 9.0


def test_replay_applies_late_actions_and_restart_clears_the_log():
    world = World(small(), seed=4)
    for _ in range(10):
        world.step()
    game = replay(world, [(3, "nutrients", 5, 5), (12, "meteorite", 20, 4)], 20)
    assert [a[1] for a in game.actions] == ["nutrients", "meteorite"]
    game.restart(seed=2)
    assert game.actions == []
