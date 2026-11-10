"""F3 sensors and directed movement."""
import math

import pytest

from worldsim import Config, World
from worldsim.persistence import load_world, save_world
from worldsim.species import genome_distance
from worldsim.world import (G_PRED, G_W_DANGER, G_W_KIN, G_W_LIGHT, G_W_ORGANIC, G_W_STRANGER, N_GENES, Cell)


def empty_world(**kw):
    base = dict(width=20, height=20, initial_cells=0, immigration_rate=0.0, sensing=True, sense_noise=0.0,
                reseed_on_extinction=False)
    base.update(kw)
    return World(Config(**base), seed=1)


def put(world, x, y, lineage=None, **genes):
    """Place a cell whose sensor weights are 0 (gene 0.5) unless given as gene index -> weight."""
    g = [0.5] * N_GENES
    for idx, w in genes.items():
        g[int(idx)] = (w + 1.0) / 2.0
    cid = world._new_id()
    c = Cell(cid, x, y, 50.0, g, cid if lineage is None else lineage, world.cfg)
    world._place(c)
    return c


def weights(**named):
    index = {"light": G_W_LIGHT, "organic": G_W_ORGANIC, "kin": G_W_KIN, "stranger": G_W_STRANGER,
             "danger": G_W_DANGER}
    return {str(index[k]): v for k, v in named.items()}


def test_zero_weights_and_no_noise_stay_put():
    w = empty_world()
    c = put(w, 10, 10)
    assert w.sensed_move(c) is None


@pytest.mark.parametrize("sign, dy", [(1.0, -1), (-1.0, 1)])
def test_phototaxis_follows_the_light_gradient(sign, dy):
    w = empty_world()
    c = put(w, 10, 10, **weights(light=sign))
    w.update_light()
    assert w.sensed_move(c)[1] == 10 + dy          # up towards the light, or down away from it


def test_attracted_to_organic_matter():
    w = empty_world()
    w.organic[10, 11] = 50.0
    c = put(w, 10, 10, **weights(organic=1.0))
    assert w.sensed_move(c) == (11, 10)


def test_flees_from_a_predator():
    w = empty_world()
    put(w, 9, 10, **{str(G_PRED): 1.0})              # a stranger predator on the left
    c = put(w, 10, 10, **weights(danger=-1.0))
    dest = w.sensed_move(c)
    assert dest is not None and dest[0] == 11       # moves to the side away from it


def test_kin_attract_and_strangers_repel():
    w = empty_world()
    put(w, 10, 9, lineage=99)                        # kin above
    c = put(w, 10, 10, lineage=99, **weights(kin=1.0))
    put(w, 10, 11)                                   # stranger below
    assert w.sensed_move(c)[1] == 9                  # towards kin, away from the stranger
    c2 = put(w, 5, 5, **weights(stranger=-1.0))
    put(w, 4, 5)
    assert w.sensed_move(c2)[0] == 6


def test_never_moves_onto_rock_or_outside_and_waits_when_boxed_in():
    w = empty_world(sense_noise=1.0)
    w.terrain.rock[5:8, 5:8] = True
    w.terrain.rock[6, 6] = False
    w.set_terrain(w.terrain)
    c = put(w, 6, 6, **weights(light=1.0))
    assert w.sensed_move(c) is None                  # every neighbour is rock
    top = put(w, 15, 0, **weights(light=1.0))
    for _ in range(50):
        dest = w.sensed_move(top)
        assert dest is None or 0 <= dest[1] < w.H


def test_sensor_genes_are_inert_when_sensing_is_off():
    cfg = dict(width=40, height=20, initial_cells=120)
    a, b = World(Config(**cfg), seed=3), World(Config(**cfg), seed=3)
    for c in b.cells:
        c.genes[G_W_LIGHT:] = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
        c.express(b.cfg)
    for _ in range(200):
        a.step()
        b.step()
    assert [(c.id, c.x, c.y, c.energy) for c in a.cells] == [(c.id, c.x, c.y, c.energy) for c in b.cells]


def test_sensing_costs_upkeep_only_when_on():
    on, off = empty_world(sense_upkeep=0.1), empty_world(sensing=False, sense_upkeep=0.1)
    c_on, c_off = put(on, 1, 1, **weights(light=1.0)), put(off, 1, 1, **weights(light=1.0))
    assert math.isclose(c_on.upkeep - c_off.upkeep, 0.1 / 6)


def test_sensing_runs_are_deterministic_and_resume_bit_exact(tmp_path):
    cfg = Config(width=40, height=20, initial_cells=120, sensing=True, day_amplitude=1.0, day_length=40)
    straight = World(cfg, seed=5)
    for _ in range(300):
        straight.step()
    first = World(cfg, seed=5)
    for _ in range(120):
        first.step()
    save_world(first, tmp_path / "w.json.gz")
    resumed = load_world(tmp_path / "w.json.gz")
    for _ in range(180):
        resumed.step()

    def key(w):
        return [(c.id, c.x, c.y, c.energy, tuple(c.genes)) for c in w.cells], w.stats()
    assert key(resumed) == key(straight)
    again = World(cfg, seed=5)
    for _ in range(300):
        again.step()
    assert key(again) == key(straight)


def test_species_distance_keeps_its_per_gene_meaning():
    a10, b10 = [0.0] * 10, [0.1] * 10
    assert math.isclose(genome_distance(a10, b10), math.dist(a10, b10))
    assert math.isclose(genome_distance([0.0] * 16, [0.1] * 16), genome_distance(a10, b10))


@pytest.mark.parametrize("field, value", [("sense_noise", -1.0), ("sense_noise", 11.0), ("sense_upkeep", 99.0)])
def test_sensing_parameters_are_bounded(field, value):
    with pytest.raises(ValueError):
        Config(**{field: value}).validate()


def test_flees_from_a_predator_of_its_own_lineage():
    w = empty_world()
    put(w, 9, 10, lineage=99, **{str(G_PRED): 1.0})  # kin predators eat kin too
    c = put(w, 10, 10, lineage=99, **weights(danger=-1.0))
    dest = w.sensed_move(c)
    assert dest is not None and dest[0] == 11


def test_social_densities_count_only_tiles_inside_the_grid():
    """On the surface row the mover has 5 neighbour tiles, not 8: four kin out of five is a density of
    0.8 for staying put. A kin weight set so that the light lost by going down is worth 0.35 of density
    keeps it at the surface; dividing by 8 (density 0.5) would send it to the free tile below (density 1)."""
    w = empty_world()
    for dx, dy in [(-1, 0), (1, 0), (-1, 1), (1, 1)]:
        put(w, 10 + dx, dy, lineage=99)
    c = put(w, 10, 0, lineage=99)
    w.update_light()
    drop = (w.light[0, 10] - w.light[1, 10]) / w.cfg.light_max
    wk = drop / 0.35
    assert 0.0 < wk <= 1.0                             # precondition: a valid weight
    c.sense = (1.0, 0.0, 0.0, wk, 0.0, 0.0)
    assert w.sensed_move(c) is None


def test_moves_across_the_wrapped_x_edge():
    w = empty_world()
    w.organic[10, w.W - 1] = 50.0
    c = put(w, 0, 10, **weights(organic=1.0))
    assert w.sensed_move(c) == (w.W - 1, 10)
