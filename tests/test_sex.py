"""F5a two parents: evolvable mating propensity, partner search, crossover."""
import json

import pytest

from worldsim import Config, World
from worldsim.persistence import SaveFormatError, load_world, save_world, world_from_dict, world_to_dict
from worldsim.world import N_GENES, Cell


def world(**kw):
    base = dict(width=20, height=20, initial_cells=0, immigration_rate=0.0, reseed_on_extinction=False, sex=True)
    base.update(kw)
    return World(Config(**base), seed=1, track_species=False)    # cells are placed by hand


def put(w, x, y, genes=None, sex_p=1.0, energy=20.0):
    cid = w._new_id()
    c = Cell(cid, x, y, energy, list(genes or [0.5] * N_GENES), cid, w.cfg, sex_p=sex_p)
    w._place(c)
    return c


def test_off_world_never_runs_mating_code(monkeypatch):
    def boom(*_):
        raise AssertionError("mating code ran with sex off")
    for name in ("find_mate", "offspring_genes", "offspring_sex_p"):
        monkeypatch.setattr(World, name, boom)
    w = World(Config(width=40, height=20, initial_cells=120, sensing=True, open_genome=True, rule_new_rate=0.3),
              seed=11)
    for _ in range(300):
        w.step()
    assert w.births > 0 and w.sex_births == 0 and all(c.sex_p == 0.0 for c in w.cells)


def test_partners_are_found_within_radius_and_genetic_distance():
    w = world(mate_radius=2, mate_distance=0.3)
    c = put(w, 10, 10)
    assert w.find_mate(c) is None                              # alone
    far = put(w, 13, 10)                                       # outside radius 2
    alien = put(w, 11, 11, genes=[1.0] * N_GENES)              # too different
    assert w.find_mate(c) is None
    near = put(w, 12, 8, genes=[0.55] * N_GENES)               # corner of the 5x5 square, similar genes
    assert w.find_mate(c) is near
    assert far is not None and alien is not None


def test_partner_search_wraps_in_x_and_stops_at_the_floor():
    w = world()
    c = put(w, 0, w.H - 1)
    mate = put(w, w.W - 2, w.H - 2)                            # two tiles to the left across the wrap
    assert w.find_mate(c) is mate


def test_crossover_takes_each_gene_from_either_parent():
    w = world()
    a, b = put(w, 1, 1, genes=[0.0] * N_GENES), put(w, 2, 1, genes=[1.0] * N_GENES)
    kids = [w.offspring_genes(a, b) for _ in range(200)]
    assert all(set(k) <= {0.0, 1.0} for k in kids)
    share = sum(sum(k) for k in kids) / (200 * N_GENES)
    assert 0.4 < share < 0.6
    assert w.offspring_genes(a, None) is a.genes


def test_sexual_division_pays_its_cost_and_counts():
    def after_one_step(cost):
        w = world(sex_cost=cost)
        c = put(w, 10, 10, energy=w.cfg.div_max + 10.0)
        put(w, 11, 10, energy=1.0)
        w.cells = [c] + [o for o in w.cells if o is not c]     # the parent acts first
        w.step()
        return w, c
    free, c_free = after_one_step(0.0)
    paid, c_paid = after_one_step(3.0)
    assert free.sex_births == paid.sex_births == 1 and paid.stats()["sex_births"] == 1
    # the cost is paid before the energy split, so the parent keeps (1 - child_frac) of it less
    assert c_free.energy - c_paid.energy == pytest.approx(3.0 * (1.0 - c_paid.child_frac))


def test_neutral_arm_inherits_and_mutates_but_never_mates():
    w = world(sex_neutral=True)
    put(w, 10, 10, sex_p=0.5, energy=w.cfg.div_max + 10.0)
    put(w, 11, 10, energy=1.0)
    for _ in range(5):
        w.step()
    children = [o for o in w.cells if o.id > 2]
    assert children and w.sex_births == 0
    assert all(o.sex_p != 0.5 for o in children)            # inherited with mutation


def test_seeded_cells_draw_a_propensity_only_when_sex_is_on():
    on = World(Config(width=20, height=10, initial_cells=30, sex=True), seed=2)
    off = World(Config(width=20, height=10, initial_cells=30), seed=2)
    assert len({c.sex_p for c in on.cells}) > 1
    assert all(c.sex_p == 0.0 for c in off.cells)


def test_sexual_runs_resume_bit_exact(tmp_path):
    cfg = Config(width=40, height=20, initial_cells=150, sex=True, sex_cost=0.5, day_amplitude=1.0, day_length=40)
    straight = World(cfg, seed=4)
    for _ in range(300):
        straight.step()
    assert straight.sex_births > 0
    first = World(cfg, seed=4)
    for _ in range(150):
        first.step()
    save_world(first, tmp_path / "w.json.gz")
    resumed = load_world(tmp_path / "w.json.gz")
    for _ in range(150):
        resumed.step()

    def key(w):
        return [(c.id, c.x, c.y, c.energy, tuple(c.genes), c.sex_p) for c in w.cells], w.stats()
    assert key(resumed) == key(straight)


def test_rejects_invalid_propensity_in_saves():
    d = world_to_dict(World(Config(width=20, height=10, initial_cells=10, sex=True), seed=1))
    for bad in (1.5, -0.1, float("nan"), True, "x", 10 ** 400):
        e = json.loads(json.dumps(d))
        e["cells"][0][10] = bad
        with pytest.raises(SaveFormatError):
            world_from_dict(e)
    off = world_to_dict(World(Config(width=20, height=10, initial_cells=10), seed=1))
    off["cells"][0][10] = 0.5                                  # a propensity in a world without sex
    with pytest.raises(SaveFormatError, match="sex_p"):
        world_from_dict(off)


@pytest.mark.parametrize("field, value", [("mate_radius", 0), ("mate_radius", 6), ("sex_cost", 11.0),
                                          ("mate_distance", -1.0)])
def test_sex_parameters_are_bounded(field, value):
    with pytest.raises(ValueError):
        Config(**{field: value}).validate()


def test_child_propensity_comes_from_the_dividing_parent_only():
    """Taking the mate's propensity would pull the mean down by itself (mates are not chosen by it)."""
    w = world()
    c = put(w, 10, 10, sex_p=0.9)
    c.mut_sigma = 0.0
    assert w.offspring_sex_p(c) == 0.9
    w2 = world()
    parent = put(w2, 10, 10, sex_p=1.0, energy=w2.cfg.div_max + 10.0)
    put(w2, 11, 10, sex_p=0.0, energy=1.0)
    w2.cells = [parent] + [o for o in w2.cells if o is not parent]
    w2.step()
    assert w2.sex_births == 1
    child = next(o for o in w2.cells if o.id > 2)
    assert child.sex_p > 1.0 - 5 * parent.mut_sigma


def test_sexual_child_carries_genes_from_both_parents():
    w = world(mate_distance=0.3)
    g_a, g_b = [0.45] * N_GENES, [0.53] * N_GENES          # distance ~0.25, within mate_distance
    g_a[8] = g_b[8] = 0.0                                   # mut gene 0: tiny mutation
    a = put(w, 10, 10, genes=g_a, energy=w.cfg.div_max + 10.0)
    put(w, 11, 10, genes=g_b, energy=1.0)
    w.cells = [a] + [o for o in w.cells if o is not a]
    w.step()
    child = next(o for o in w.cells if o.id > 2)
    near_a = sum(abs(v - 0.45) < 0.03 for i, v in enumerate(child.genes) if i != 8)
    near_b = sum(abs(v - 0.53) < 0.03 for i, v in enumerate(child.genes) if i != 8)
    assert near_a > 0 and near_b > 0 and near_a + near_b == N_GENES - 1


def test_expensive_sex_is_skipped_rather_than_driving_energy_negative():
    w = world(sex_cost=10.0)
    genes = [0.5] * N_GENES
    genes[4] = 0.0                                          # div gene 0: divides at div_min
    c = put(w, 10, 10, genes=genes, energy=w.cfg.div_min + 1.0)   # affords the body, not body + sex
    put(w, 11, 10, energy=1.0)
    w.cells = [c] + [o for o in w.cells if o is not c]
    w.step()
    assert w.sex_births == 0 and w.births == 1
    assert all(o.energy >= 0.0 for o in w.cells)


def test_partner_search_does_not_wrap_vertically():
    w = world()
    c = put(w, 5, 0)
    put(w, 5, w.H - 1)                                      # reachable only through a negative-index bug
    assert w.find_mate(c) is None


def test_partner_search_counts_each_tile_once_on_a_narrow_world():
    """Width 4, radius 2: from x=1 the wrap visits x=3 twice and x=0 once; each mate must be equally likely."""
    w = world(width=4, mate_radius=2)
    c = put(w, 1, 5)
    twice, once = put(w, 3, 5), put(w, 0, 5)
    picks = [w.find_mate(c) for _ in range(600)]
    assert set(picks) == {twice, once}
    assert 240 < picks.count(twice) < 360                   # ~300; a double-counted tile would give ~400


def test_species_tracking_does_not_change_a_sexual_history():
    cfg = Config(width=40, height=20, initial_cells=150, sex=True, sex_cost=0.5)
    a, b = World(cfg, seed=8), World(cfg, seed=8, track_species=False)
    for _ in range(200):
        a.step()
        b.step()
    assert a.sex_births > 0
    assert [(c.id, c.x, c.y, c.energy, c.sex_p) for c in a.cells] == [(c.id, c.x, c.y, c.energy, c.sex_p)
                                                                       for c in b.cells]


@pytest.mark.parametrize("extra", [dict(open_genome=True, rule_new_rate=0.3, sensing=True),
                                   dict(sex_neutral=True)])
def test_resume_is_bit_exact_with_other_features(tmp_path, extra):
    cfg = Config(width=40, height=20, initial_cells=150, sex=True, **extra)
    straight = World(cfg, seed=6)
    for _ in range(240):
        straight.step()
    first = World(cfg, seed=6)
    for _ in range(120):
        first.step()
    save_world(first, tmp_path / "w.json.gz")
    resumed = load_world(tmp_path / "w.json.gz")
    for _ in range(120):
        resumed.step()

    def key(w):
        return [(c.id, c.energy, tuple(c.genes), tuple(map(tuple, c.rules)), c.sex_p) for c in w.cells], w.stats()
    assert key(resumed) == key(straight)
