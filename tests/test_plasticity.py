"""F5b plasticity: within-life diet acclimation with an evolvable rate."""
import json

import pytest

from worldsim import Config, World
from worldsim.persistence import SaveFormatError, load_world, save_world, world_from_dict, world_to_dict
from worldsim.world import G_CHEMO, G_PHOTO, G_PRED, G_SAPRO, N_GENES, TRAIT_NAMES, Cell, genetic_diet, make_traits


def world(**kw):
    base = dict(width=20, height=20, initial_cells=0, immigration_rate=0.0, reseed_on_extinction=False,
                plasticity=True)
    base.update(kw)
    return World(Config(**base), seed=1, track_species=False)    # cells are placed by hand


def mixed_genes():
    g = [0.5] * N_GENES
    g[G_PHOTO], g[G_SAPRO], g[G_PRED], g[G_CHEMO] = 0.5, 0.5, 0.0, 0.0
    return g


def put(w, x, y, plast_p=1.0, energy=20.0, genes=None):
    cid = w._new_id()
    c = Cell(cid, x, y, energy, genes or mixed_genes(), cid, w.cfg, traits=make_traits(plast_p=plast_p))
    w._place(c)
    return c


def test_off_world_never_runs_plasticity_code(monkeypatch):
    def boom(*_):
        raise AssertionError("plasticity code ran with plasticity off")
    monkeypatch.setattr(World, "acclimate", boom)
    inherit = World.offspring_traits     # shared with the traits that are on: plast_p must stay out of it

    def checked(self, c):
        traits = inherit(self, c)
        assert traits[TRAIT_NAMES.index("plast_p")] == 0.0, "plasticity code ran with plasticity off"
        return traits
    monkeypatch.setattr(World, "offspring_traits", checked)
    monkeypatch.setattr(Cell, "apply_diet", boom)
    w = World(Config(width=40, height=20, initial_cells=120, sensing=True, open_genome=True, sex=True), seed=11)
    for _ in range(300):
        w.step()
    assert w.births > 0 and all(c.plast_p == 0.0 and c.diet == () for c in w.cells)
    assert w.stats()["diet_shift"] == 0.0


def test_genetic_diet_at_birth_keeps_the_phenotype():
    w = world()
    c = put(w, 5, 5)
    assert c.diet == pytest.approx((0.5, 0.5, 0.0))
    assert (c.photo, c.sapro, c.pred, c.chemo) == pytest.approx((0.5, 0.5, 0.0, 0.0))
    assert genetic_diet(0.0, 0.0, 0.0) == pytest.approx((1 / 3, 1 / 3, 1 / 3))


def test_diet_moves_towards_the_resource_present_here():
    w = world(plastic_rate=0.1)
    c = put(w, 5, 5)
    w.acclimate(c, 1.0, 0.0, 0.0)                               # light only
    assert c.diet[0] == pytest.approx(0.5 + 0.1 * 0.5) and sum(c.diet) == pytest.approx(1.0)
    assert c.photo > 0.5 and c.photo_k == pytest.approx(c.photo ** w.cfg.spec_exp)
    before = c.diet
    w.acclimate(c, 0.0, 0.0, 0.0)                               # nothing to gain: no move
    assert c.diet == before
    for _ in range(500):
        w.acclimate(c, 0.0, 5.0, 0.0)                           # organic only
    assert c.diet[1] > 0.99


def test_predation_share_stays_genetic():
    w = world(plastic_rate=1.0)
    g = mixed_genes()
    g[G_PRED] = 0.5
    c = put(w, 5, 5, genes=g)
    pred = c.pred
    w.acclimate(c, 1.0, 0.0, 0.0)
    assert c.pred == pred and c.photo + c.sapro + c.chemo == pytest.approx(1.0 - pred)


def test_rate_scales_with_plast_p_and_zero_means_fixed():
    w = world(plastic_rate=0.1)
    fast, slow = put(w, 1, 1, plast_p=1.0), put(w, 3, 1, plast_p=0.2)
    for c in (fast, slow):
        w.acclimate(c, 1.0, 0.0, 0.0)
    assert fast.diet[0] - 0.5 == pytest.approx(5 * (slow.diet[0] - 0.5))
    still = put(w, 5, 1, plast_p=0.0)
    w.step()
    assert still.diet == pytest.approx((0.5, 0.5, 0.0))


def test_upkeep_pays_for_plasticity_in_both_arms():
    on, neutral = world(plastic_upkeep=0.2), world(plastic_upkeep=0.2, plastic_neutral=True)
    off = World(Config(width=20, height=20, initial_cells=0), seed=1, track_species=False)
    a, b = put(on, 1, 1, plast_p=0.5), put(neutral, 1, 1, plast_p=0.5)
    cid = off._new_id()
    base = Cell(cid, 1, 1, 20.0, mixed_genes(), cid, off.cfg)
    assert a.upkeep == b.upkeep == pytest.approx(base.upkeep + 0.1)


def test_neutral_arm_inherits_and_mutates_but_diet_never_moves():
    w = world(plastic_neutral=True, light_depth=1000.0)
    put(w, 10, 0, plast_p=0.5, energy=w.cfg.div_max + 10.0)
    for _ in range(5):
        w.step()
    children = [o for o in w.cells if o.id > 1]
    assert children and all(o.plast_p != 0.5 for o in children)          # inherited with mutation
    assert all(World.diet_shift(o) < 1e-12 for o in w.cells)               # rounding only


def test_children_restart_from_the_genetic_diet():
    w = world(plastic_rate=1.0, light_depth=1000.0)
    p = put(w, 10, 0, energy=w.cfg.div_max + 10.0)
    w.cells = [p]
    w.step()
    kids = [o for o in w.cells if o is not p]
    assert kids and World.diet_shift(p) > 0.0
    for k in kids:
        g = k.genes
        assert k.diet == pytest.approx(genetic_diet(g[G_PHOTO], g[G_SAPRO], g[G_CHEMO]))


def test_seeded_cells_draw_a_rate_only_when_plasticity_is_on():
    on = World(Config(width=20, height=10, initial_cells=30, plasticity=True), seed=2)
    off = World(Config(width=20, height=10, initial_cells=30), seed=2)
    assert len({c.plast_p for c in on.cells}) > 1
    assert all(c.plast_p == 0.0 for c in off.cells)


def test_plastic_runs_resume_bit_exact(tmp_path):
    cfg = Config(width=40, height=20, initial_cells=150, plasticity=True, plastic_rate=0.2, vent_count=2,
                 day_amplitude=1.0, day_length=40)
    straight = World(cfg, seed=4)
    for _ in range(300):
        straight.step()
    assert straight.stats()["diet_shift"] > 0.0
    first = World(cfg, seed=4)
    for _ in range(150):
        first.step()
    save_world(first, tmp_path / "w.json.gz")
    resumed = load_world(tmp_path / "w.json.gz")
    for _ in range(150):
        resumed.step()

    def key(w):
        return [(c.id, c.x, c.y, c.energy, tuple(c.genes), c.plast_p, c.diet, c.photo) for c in w.cells], w.stats()
    assert key(resumed) == key(straight)


def test_rejects_invalid_plasticity_state_in_saves():
    d = world_to_dict(World(Config(width=20, height=10, initial_cells=10, plasticity=True), seed=1))
    world_from_dict(json.loads(json.dumps(d)))                  # the untouched save loads
    for col, bad in [(11, 1.5), (11, float("nan")), (11, True), (11, "x"), (12, [0.5, 0.5]),
                     (12, [0.9, 0.9, 0.1]), (12, [1.5, -0.25, -0.25]), (12, "abc"), (12, [])]:
        e = json.loads(json.dumps(d))
        e["cells"][0][col] = bad
        with pytest.raises(SaveFormatError):
            world_from_dict(e)
    off = world_to_dict(World(Config(width=20, height=10, initial_cells=10), seed=1))
    for col, bad in [(11, 0.5), (12, [1.0, 0.0, 0.0])]:          # state present while the flag is off
        e = json.loads(json.dumps(off))
        e["cells"][0][col] = bad
        with pytest.raises(SaveFormatError):
            world_from_dict(e)


def test_cell_without_feeding_genes_cannot_feed_in_any_arm():
    # Review finding: with all four feeding genes at 0 the off-world gives shares 0, but the plastic phenotype
    # used to fall back to a 1/3 generalist split (and could even acclimate into a specialist).
    g = mixed_genes()
    g[G_PHOTO] = g[G_SAPRO] = g[G_PRED] = g[G_CHEMO] = 0.0
    for kw in ({}, {"plastic_neutral": True}):
        w = world(plastic_rate=1.0, **kw)
        c = put(w, 5, 5, genes=list(g))
        w.acclimate(c, 1.0, 1.0, 1.0)
        assert (c.photo, c.sapro, c.pred, c.chemo) == (0.0, 0.0, 0.0, 0.0)
        assert c.photo_k == c.sapro_k == c.chemo_k == 0.0


def test_loader_rejects_a_diet_that_could_not_have_moved():
    w = world(plastic_neutral=True)
    put(w, 5, 5, plast_p=0.5)
    d = world_to_dict(w)
    d["cells"][0][12] = [1.0, 0.0, 0.0]                         # neutral arm: the diet never leaves the genes
    with pytest.raises(SaveFormatError):
        world_from_dict(json.loads(json.dumps(d)))
    w = world()
    put(w, 5, 5, plast_p=0.0)
    d = world_to_dict(w)
    d["cells"][0][12] = [1.0, 0.0, 0.0]                         # plast_p 0: same
    with pytest.raises(SaveFormatError):
        world_from_dict(json.loads(json.dumps(d)))
