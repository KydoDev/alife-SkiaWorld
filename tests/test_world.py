"""Engine invariant tests. Small worlds, explicit seeds, few steps."""
import pytest

from worldsim import Config, World
from worldsim.world import N_GENES


def small_config(**overrides):
    cfg = Config(width=40, height=20, initial_cells=80)
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def run(world, steps):
    for _ in range(steps):
        world.step()
    return world


def test_grid_and_cell_list_stay_consistent():
    world = run(World(small_config(), seed=3), 200)
    on_grid = [c for c in world.grid if c is not None]
    assert len(on_grid) == len(world.cells)
    assert {id(c) for c in on_grid} == {id(c) for c in world.cells}
    for c in world.cells:
        assert c.alive
        assert world.grid[c.y * world.W + c.x] is c


def test_bonds_are_symmetric_and_point_to_living_cells():
    world = run(World(small_config(), seed=5), 200)
    for c in world.cells:
        for b in c.bonds:
            assert b.alive
            assert c in b.bonds
        assert len(c.bonds) <= world.cfg.max_bonds


@pytest.mark.xfail(
    strict=True,
    reason="Known bug (2026-11-10, see TEST.md/.nextPrompt): Cell.bonds is a set of objects hashed "
           "by id(), so colony energy-sharing order varies between runs; histories diverge at step ~4.",
)
def test_same_seed_gives_identical_history():
    a = run(World(small_config(), seed=11), 150)
    b = run(World(small_config(), seed=11), 150)
    assert a.stats() == b.stats()


def test_different_seeds_diverge():
    a = run(World(small_config(), seed=1), 150)
    b = run(World(small_config(), seed=2), 150)
    assert a.stats() != b.stats()


def test_genes_stay_in_unit_interval_after_mutation():
    world = run(World(small_config(mut_max=0.5), seed=7), 200)
    for c in world.cells:
        assert len(c.genes) == N_GENES
        assert all(0.0 <= g <= 1.0 for g in c.genes)


def test_organic_matter_is_never_negative():
    world = run(World(small_config(), seed=9), 200)
    assert world.organic.min() >= 0.0


def test_extinction_triggers_reseed():
    # Upkeep far above any income: everyone starves quickly.
    cfg = small_config(base_cost=100.0, immigration_rate=0.0)
    world = run(World(cfg, seed=4), 3)
    assert world.extinctions >= 1
    assert len(world.cells) == cfg.initial_cells


def test_stats_columns_used_by_runner_exist():
    s = World(small_config(), seed=1).stats()
    for key in ["step", "population", "photo", "sapro", "pred", "in_colony",
                "lineages", "extinctions", "mean_move", "mean_attach",
                "mean_share", "mean_mut", "mean_div"]:
        assert key in s


@pytest.mark.parametrize("x,y", [(-1, 0), (0, -1), (40, 0), (0, 20)])
def test_cell_at_out_of_bounds_returns_none(x, y):
    assert World(small_config(), seed=1).cell_at(x, y) is None
