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


def assert_grid_consistent(world):
    on_grid = [c for c in world.grid if c is not None]
    assert len(on_grid) == len(world.cells)
    assert {id(c) for c in on_grid} == {id(c) for c in world.cells}
    for c in world.cells:
        assert c.alive, f"dead cell #{c.id} left in the cell list at step {world.step_count}"
        assert world.grid[c.y * world.W + c.x] is c


def test_grid_and_cell_list_stay_consistent():
    # Checked after every step: a newborn eaten in its birth step used to stay in
    # `cells` as a dead ghost for one step (regression, 2026-11-10).
    world = World(small_config(), seed=3)
    for _ in range(200):
        world.step()
        assert_grid_consistent(world)


def test_bonds_are_symmetric_and_point_to_living_cells():
    world = run(World(small_config(), seed=5), 200)
    for c in world.cells:
        for b in c.bonds:
            assert b.alive
            assert c in b.bonds
        assert len(c.bonds) <= world.cfg.max_bonds


def test_same_seed_gives_identical_history():
    # Regression (2026-11-10): Cell.bonds was a set hashed by id(), so colony
    # energy-sharing order varied between runs and histories diverged at step ~4.
    a = World(small_config(), seed=11)
    b = World(small_config(), seed=11)
    for _ in range(300):
        a.step()
        b.step()
        assert a.stats() == b.stats(), f"diverged at step {a.step_count}"
    assert [(c.id, c.x, c.y, c.energy) for c in a.cells] == [(c.id, c.x, c.y, c.energy) for c in b.cells]


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


def total_energy(world):
    """Energy in cells + energy locked in bodies + organic matter."""
    cells = world.cells
    return sum(c.energy for c in cells) + len(cells) * world.cfg.body_cost + float(world.organic.sum())


def test_energy_is_conserved_in_a_closed_system():
    # Every source and sink switched off: no light income, no upkeep or movement
    # cost, no organic decay, lossless decomposition/feeding, no immigration.
    # Predation, sharing, division, death, diffusion and sinking must only move energy.
    cfg = small_config(
        photo_gain=0.0, base_cost=0.0, pred_upkeep=0.0, move_upkeep=0.0, move_cost=0.0,
        organic_decay=0.0, decomp_fraction=1.0, sapro_eff=1.0,
        immigration_rate=0.0, reseed_on_extinction=False, max_age=50,
    )
    world = World(cfg, seed=13)
    start = total_energy(world)
    births_seen = deaths_seen = False
    for _ in range(200):
        world.step()
        births_seen |= world.births > 0
        deaths_seen |= world.deaths > 0
        assert total_energy(world) == pytest.approx(start, rel=1e-9)
    # Make sure the test actually exercised the transfers it claims to cover.
    assert births_seen and deaths_seen and world.kills > 0


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
