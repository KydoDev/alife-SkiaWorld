"""F5c horizontal gene transfer: a cell copies one fixed gene from a neighbour, with an evolvable propensity."""
import json

import pytest

from worldsim import Config, World
from worldsim.persistence import SaveFormatError, load_world, save_world, world_from_dict, world_to_dict
from worldsim.world import G_CHEMO, G_PHOTO, G_PRED, G_SAPRO, N_GENES, TRAIT_NAMES, Cell, genetic_diet, make_traits

HGT_COL = 13                                                     # hgt_p in a v7 cell row


def world(**kw):
    base = dict(width=20, height=20, initial_cells=0, immigration_rate=0.0, reseed_on_extinction=False, hgt=True)
    base.update(kw)
    return World(Config(**base), seed=1, track_species=False)    # cells are placed by hand


def put(w, x, y, value, hgt_p=1.0, energy=20.0, lineage=None, plast_p=0.0):
    cid = w._new_id()
    c = Cell(cid, x, y, energy, [value] * N_GENES, cid if lineage is None else lineage, w.cfg,
             traits=make_traits(hgt_p=hgt_p, plast_p=plast_p))
    w._place(c)
    return c


def test_off_world_never_runs_transfer_code(monkeypatch):
    def boom(*_):
        raise AssertionError("transfer code ran with hgt off")
    monkeypatch.setattr(World, "transfer_gene", boom)
    inherit = World.offspring_traits     # shared with the traits that are on: hgt_p must stay out of it

    def checked(self, c):
        traits = inherit(self, c)
        assert traits[TRAIT_NAMES.index("hgt_p")] == 0.0, "transfer code ran with hgt off"
        return traits
    monkeypatch.setattr(World, "offspring_traits", checked)
    w = World(Config(width=40, height=20, initial_cells=120, sensing=True, open_genome=True, sex=True,
                     plasticity=True), seed=11)
    for _ in range(300):
        w.step()
    assert w.births > 0 and all(c.hgt_p == 0.0 for c in w.cells)
    s = w.stats()
    assert s["hgt_events"] == s["hgt_foreign"] == 0 and s["hgt_p_mean"] == 0.0


def test_transfer_copies_one_gene_from_a_neighbour_and_re_expresses():
    w = world()
    c = put(w, 5, 5, 0.2)
    d = put(w, 6, 5, 0.9)
    old = c.genes
    w.transfer_gene(c)
    changed = [k for k in range(N_GENES) if c.genes[k] != 0.2]
    assert len(changed) == 1 and c.genes[changed[0]] == 0.9
    assert old == [0.2] * N_GENES                                 # a new list: nothing aliased is edited
    assert d.genes == [0.9] * N_GENES                             # the donor keeps its genes
    fresh = Cell(99, 0, 0, 1.0, list(c.genes), 99, w.cfg, traits=make_traits(hgt_p=c.hgt_p))
    assert (c.photo, c.upkeep, c.div_thr, c.mut_sigma) == (fresh.photo, fresh.upkeep, fresh.div_thr,
                                                           fresh.mut_sigma)
    assert w.hgt_events == 1 and w.hgt_foreign == 1               # the donor has another lineage


def test_same_lineage_donor_is_not_counted_foreign_and_lonely_cell_is_unchanged():
    w = world()
    c = put(w, 5, 5, 0.2)
    put(w, 5, 6, 0.9, lineage=c.lineage)
    w.transfer_gene(c)
    assert w.hgt_events == 1 and w.hgt_foreign == 0
    lone = put(w, 15, 15, 0.3)
    w.transfer_gene(lone)
    assert lone.genes == [0.3] * N_GENES and w.hgt_events == 1


def test_step_transfers_at_the_rate_set_by_hgt_p():
    w = world(hgt_rate=1.0, max_age=10**6, base_cost=0.0, light_depth=1000.0, div_min=1e3, div_max=1e3)
    c = put(w, 5, 5, 0.2, hgt_p=1.0, energy=500.0)
    put(w, 6, 5, 0.9, hgt_p=0.0, energy=500.0)
    w.cells = w.cells[:2]
    w.step()
    assert w.hgt_events == 1 and sum(v == 0.9 for v in c.genes) == 1   # the cell with hgt_p 0 copies nothing


def test_upkeep_is_paid_in_both_arms():
    for kw in ({}, {"hgt_neutral": True}):
        w = world(hgt_upkeep=0.3, **kw)
        c = put(w, 5, 5, 0.5, hgt_p=0.5)
        off = Cell(99, 0, 0, 1.0, [0.5] * N_GENES, 99, Config(width=20, height=20))
        assert c.upkeep == pytest.approx(off.upkeep + 0.15)


def test_neutral_arm_inherits_and_mutates_but_never_transfers():
    w = World(Config(width=40, height=20, initial_cells=150, hgt=True, hgt_neutral=True, hgt_rate=1.0), seed=3)
    for _ in range(200):
        w.step()
    assert w.hgt_events == 0 and w.births > 0
    assert len({c.hgt_p for c in w.cells}) > 10                       # inherited with mutation


def test_children_inherit_the_transferred_genome():
    w = world(hgt_rate=1.0, light_depth=1000.0)
    p = put(w, 10, 0, 0.2, energy=w.cfg.div_max + 10.0)
    put(w, 11, 0, 0.9, hgt_p=0.0, energy=1.0)
    w.cells = w.cells[:2]
    w.transfer_gene(p)
    k = next(i for i, v in enumerate(p.genes) if v == 0.9)
    w.step()
    kids = [o for o in w.cells if o.id > 1]
    assert kids and all(abs(o.genes[k] - 0.9) < 0.2 for o in kids)


def test_transfer_resets_an_acclimated_diet_to_the_new_genetic_split():
    w = world(plasticity=True, plastic_rate=1.0)
    c = put(w, 5, 5, 0.5, plast_p=1.0)
    put(w, 6, 5, 0.9)
    w.acclimate(c, 1.0, 0.0, 0.0)
    assert World.diet_shift(c) > 0.0
    w.transfer_gene(c)
    g = c.genes
    assert c.diet == pytest.approx(genetic_diet(g[G_PHOTO], g[G_SAPRO], g[G_CHEMO]))
    assert c.pred == pytest.approx(g[G_PRED] / (g[G_PHOTO] + g[G_SAPRO] + g[G_PRED] + g[G_CHEMO]))


def test_seeded_cells_and_immigrants_draw_hgt_p_only_when_on():
    on = World(Config(width=20, height=10, initial_cells=30, hgt=True, immigration_rate=3.0), seed=2)
    off = World(Config(width=20, height=10, initial_cells=30, immigration_rate=3.0), seed=2)
    on.step()
    off.step()
    assert len({c.hgt_p for c in on.cells}) > 20
    assert all(c.hgt_p == 0.0 for c in off.cells)


@pytest.mark.parametrize("extra", [dict(vent_count=2, day_amplitude=1.0, day_length=40),
                                   dict(plasticity=True, plastic_rate=0.2, day_amplitude=1.0, day_length=40),
                                   dict(sex=True, open_genome=True, rule_new_rate=0.3)])
def test_transfer_runs_resume_bit_exact(tmp_path, extra):
    cfg = Config(width=40, height=20, initial_cells=150, hgt=True, hgt_rate=0.5, **extra)
    straight = World(cfg, seed=4)
    for _ in range(300):
        straight.step()
    assert straight.hgt_events > 0
    first = World(cfg, seed=4)
    for _ in range(150):
        first.step()
    save_world(first, tmp_path / "w.json.gz")
    resumed = load_world(tmp_path / "w.json.gz")
    for _ in range(150):
        resumed.step()

    def key(w):
        return ([(c.id, c.x, c.y, c.energy, tuple(c.genes), c.hgt_p, c.plast_p, c.diet, c.photo) for c in w.cells],
                w.stats(), w.rng.getstate())
    assert key(resumed) == key(straight)


def test_rejects_invalid_transfer_state_in_saves():
    d = world_to_dict(World(Config(width=20, height=10, initial_cells=10, hgt=True), seed=1))
    world_from_dict(json.loads(json.dumps(d)))                  # the untouched save loads
    for bad in (1.5, -0.1, float("nan"), True, "x", None):
        e = json.loads(json.dumps(d))
        e["cells"][0][HGT_COL] = bad
        with pytest.raises(SaveFormatError):
            world_from_dict(e)
    for bad in (-1, 1.5, True, "3"):
        e = json.loads(json.dumps(d))
        e["counters"]["hgt_events"] = bad
        with pytest.raises(SaveFormatError):
            world_from_dict(e)
    e = json.loads(json.dumps(d))
    e["counters"]["hgt_foreign"] = e["counters"]["hgt_events"] + 1   # more foreign transfers than transfers
    with pytest.raises(SaveFormatError):
        world_from_dict(e)
    e = json.loads(json.dumps(d))
    e["cells"][0] = e["cells"][0][:HGT_COL]                     # a v6-length row
    with pytest.raises(SaveFormatError):
        world_from_dict(e)
    off = world_to_dict(World(Config(width=20, height=10, initial_cells=10), seed=1))
    e = json.loads(json.dumps(off))
    e["cells"][0][HGT_COL] = 0.5                                # state present while the flag is off
    with pytest.raises(SaveFormatError):
        world_from_dict(e)
