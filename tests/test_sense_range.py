"""ADR-0014 perception radius: an evolvable sense_r widens what a sensing cell sees, from radius 1 to
sense_radius_max; the move itself stays one tile."""
import json

import pytest

from worldsim import Config, World
from worldsim.persistence import SaveFormatError, load_world, save_world, world_from_dict, world_to_dict
from worldsim.world import G_W_KIN, N_GENES, TRAIT_NAMES, Cell, make_traits, sense_radius

SENSE_COL = 15                                                   # sense_r in a v9 cell row


def world(seed=1, **kw):
    base = dict(width=20, height=12, initial_cells=0, immigration_rate=0.0, reseed_on_extinction=False,
                sensing=True, sense_range=True)
    base.update(kw)
    return World(Config(**base), seed=seed, track_species=False)    # cells are placed by hand


def put(w, x, y, genes=None, sense_r=0.0, lineage=None):
    cid = w._new_id()
    c = Cell(cid, x, y, 20.0, list(genes or [0.5] * N_GENES), cid if lineage is None else lineage, w.cfg,
             traits=make_traits(sense_r=sense_r))
    w._place(c)
    return c


def test_radius_runs_from_one_to_the_maximum():
    assert [sense_radius(v, 3) for v in (0.0, 0.33, 0.34, 0.66, 0.67, 0.99, 1.0)] == [1, 1, 2, 2, 3, 3, 3]
    assert sense_radius(1.0, 1) == 1 and sense_radius(0.5, 5) == 3


def test_config_refuses_a_radius_sensing_cannot_use():
    with pytest.raises(ValueError, match="needs sensing"):
        Config(sense_range=True).validate()
    with pytest.raises(ValueError, match="width"):
        Config(width=6, initial_cells=0, sensing=True, sense_range=True, sense_radius_max=3).validate()
    Config(width=7, initial_cells=0, sensing=True, sense_range=True, sense_radius_max=3).validate()
    for bad in (0, 6):
        with pytest.raises(ValueError, match="sense_radius_max"):
            Config(sense_radius_max=bad).validate()


def test_upkeep_follows_the_genetic_radius_also_in_the_neutral_arm():
    for neutral in (False, True):
        w = world(sense_range_neutral=neutral, sense_radius_max=3, sense_range_upkeep=0.25)
        far, near = put(w, 3, 3, sense_r=1.0), put(w, 9, 3, sense_r=0.0)
        assert far.upkeep - near.upkeep == pytest.approx(0.25 * 2)
        assert (far.sense_rad, near.sense_rad) == ((1, 1) if neutral else (3, 1))
    off = World(Config(width=20, height=12, initial_cells=0, sensing=True), seed=1)
    c = Cell(1, 3, 3, 20.0, [0.5] * N_GENES, 1, off.cfg)
    assert c.sense_r == 0.0 and c.sense_rad == 1


def test_off_world_never_draws_or_carries_sense_r(monkeypatch):
    inherit = World.offspring_traits

    def checked(self, c):
        traits = inherit(self, c)
        assert traits[TRAIT_NAMES.index("sense_r")] == 0.0, "sense_r code ran with sense_range off"
        return traits
    monkeypatch.setattr(World, "offspring_traits", checked)
    w = World(Config(width=40, height=20, initial_cells=120, sensing=True, defence=True, hgt=True), seed=5)
    for _ in range(200):
        w.step()
    assert w.births > 0 and all(c.sense_r == 0.0 and c.sense_rad == 1 for c in w.cells)
    assert w.stats()["sense_r_mean"] == 0.0


def test_the_wide_move_at_radius_one_decides_like_f3():
    # sensed_move keeps F3's own code at R = 1; the general one, forced to R = 1, must make the same choices
    # with the same draws (scores may differ in the last bit: the product order differs), on rock, vents,
    # the surface and the floor rows
    checked = 0
    for seed in range(6):
        w = World(Config(width=12, height=8, initial_cells=60, sensing=True, rock_fraction=0.3, vent_count=2,
                         immigration_rate=0.0), seed=seed)
        for _ in range(20):
            w.step()
        for c in list(w.cells):
            state = w.rng.getstate()
            f3 = w.sensed_move(c)
            after = w.rng.getstate()
            w.rng.setstate(state)
            assert w.sensed_move_wide(c, c.sense, 1) == f3
            assert w.rng.getstate() == after
            checked += 1
    assert checked > 100


def kin_seeker():
    genes = [0.5] * N_GENES
    genes[10:16] = [0.5] * 6                                       # every sensor weight 0 ...
    genes[G_W_KIN] = 1.0                                           # ... except kin attraction
    return genes


@pytest.mark.parametrize("sense_r, moves", [(0.0, False), (1.0, True)])
def test_a_wider_radius_sees_kin_three_tiles_away(sense_r, moves):
    w = world(sense_noise=0.0, sense_radius_max=3)
    mover = put(w, 5, 5, kin_seeker(), sense_r=sense_r)
    put(w, 8, 5, lineage=mover.lineage)                            # kin at distance 3: invisible at radius 1
    dest = w.sensed_move(mover)
    if moves:
        assert dest is not None and dest[0] == 6                   # one tile towards it
    else:
        assert dest is None                                        # nothing seen, no noise: stays put


def test_the_neutral_arm_keeps_radius_one():
    w = world(sense_noise=0.0, sense_radius_max=3, sense_range_neutral=True)
    mover = put(w, 5, 5, kin_seeker(), sense_r=1.0)
    put(w, 8, 5, lineage=mover.lineage)
    assert w.sensed_move(mover) is None


def test_founders_and_children_carry_sense_r():
    w = World(Config(width=40, height=20, initial_cells=150, sensing=True, sense_range=True,
                     immigration_rate=0.0), seed=3)
    assert len({c.sense_r for c in w.cells}) > 100                  # drawn per seeded cell
    for _ in range(200):
        w.step()
    kids = [c for c in w.cells if c.id != c.lineage]
    assert w.births > 0 and kids and all(0.0 <= c.sense_r <= 1.0 for c in kids)
    assert {c.sense_rad for c in w.cells} > {1}
    assert w.stats()["sense_r_mean"] > 0.0


@pytest.mark.parametrize("extra", [{}, dict(sense_range_neutral=True), dict(vent_count=2, rock_fraction=0.2)])
def test_sense_range_runs_resume_bit_exact(tmp_path, extra):
    cfg = Config(width=40, height=20, initial_cells=150, sensing=True, sense_range=True, **extra)
    straight = World(cfg, seed=4)
    for _ in range(200):
        straight.step()
    first = World(cfg, seed=4)
    for _ in range(100):
        first.step()
    save_world(first, tmp_path / "w.json.gz")
    resumed = load_world(tmp_path / "w.json.gz")
    for _ in range(100):
        resumed.step()

    def key(w):
        return ([(c.id, c.x, c.y, c.energy, tuple(c.genes), c.sense_r) for c in w.cells],
                w.stats(), w.rng.getstate())
    assert key(resumed) == key(straight)


def test_rejects_invalid_sense_r_in_saves():
    d = world_to_dict(World(Config(width=20, height=10, initial_cells=10, sensing=True, sense_range=True), seed=1))
    world_from_dict(json.loads(json.dumps(d)))
    for bad in (1.5, -0.1, float("nan"), True, "x", None):
        e = json.loads(json.dumps(d))
        e["cells"][0][SENSE_COL] = bad
        with pytest.raises(SaveFormatError):
            world_from_dict(e)
    e = json.loads(json.dumps(d))
    e["cells"][0] = e["cells"][0][:SENSE_COL]                   # a v8-length row
    with pytest.raises(SaveFormatError):
        world_from_dict(e)
    e = json.loads(json.dumps(d))
    e["version"] = 8
    with pytest.raises(SaveFormatError, match="version 8"):
        world_from_dict(e)
    off = world_to_dict(World(Config(width=20, height=10, initial_cells=10), seed=1))
    e = json.loads(json.dumps(off))
    e["cells"][0][SENSE_COL] = 0.5                              # state present while the flag is off
    with pytest.raises(SaveFormatError):
        world_from_dict(e)


def test_the_wide_move_is_repeatable_and_draws_once_per_candidate():
    w = world(seed=9, initial_cells=80, sense_radius_max=5, width=24)
    for _ in range(30):
        w.step()
    movers = [c for c in w.cells if c.sense_rad > 1]
    assert movers
    draw = w.rng.random
    for c in movers[:20]:
        free = sum(1 for nx, ny in w.neighbors(c.x, c.y)
                   if w.grid[ny * w.W + nx] is None and not w.blocked[ny * w.W + nx])
        draws = []
        w.rng.random = lambda log=draws: log.append(1) or draw()   # count the noise draws (instance attribute)
        state = w.rng.getstate()
        a = w.sensed_move(c)
        after = w.rng.getstate()
        del w.rng.random
        assert len(draws) == (1 + free if free else 0)       # stay put + each free neighbour, none if boxed in
        w.rng.setstate(state)
        assert w.sensed_move(c) == a and w.rng.getstate() == after
