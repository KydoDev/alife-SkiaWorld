"""F5e prey defence: an evolvable armour armor_p makes an attack fail with chance armor_p x defence_strength."""
import json

import pytest

from worldsim import Config, World
from worldsim.persistence import SaveFormatError, load_world, save_world, world_from_dict, world_to_dict
from worldsim.world import G_CHEMO, G_PHOTO, G_PRED, G_SAPRO, N_GENES, TRAIT_NAMES, Cell, make_traits

ARMOR_COL = 14                                                   # armor_p in a cell row (v8 on)


def world(seed=1, **kw):
    base = dict(width=20, height=20, initial_cells=0, immigration_rate=0.0, reseed_on_extinction=False,
                defence=True)
    base.update(kw)
    return World(Config(**base), seed=seed, track_species=False)    # cells are placed by hand


def put(w, x, y, genes, armor_p=0.0, energy=20.0):
    cid = w._new_id()
    c = Cell(cid, x, y, energy, list(genes), cid, w.cfg, traits=make_traits(armor_p=armor_p))
    w._place(c)
    return c


def hunter_and_prey(w, armor_p):
    """A pure predator next to a pure phototroph; both too poor to divide, lit and long-lived."""
    pred = [0.5] * N_GENES
    pred[G_PRED], pred[G_PHOTO], pred[G_SAPRO], pred[G_CHEMO] = 1.0, 0.0, 0.0, 0.0   # predation is its only food
    prey = [0.5] * N_GENES
    prey[G_PRED] = 0.0
    hunter = put(w, 5, 5, pred, energy=50.0)
    target = put(w, 6, 5, prey, armor_p=armor_p, energy=50.0)
    w.cells = [hunter, target]
    return hunter, target


def test_off_world_never_runs_defence_code(monkeypatch):
    # the other traits are on, so children run the shared trait code: armour must stay out of it (its "no draw"
    # is proven by the golden sets of the other flags, whose hashes did not move when the code was shared)
    inherit = World.offspring_traits

    def checked(self, c):
        traits = inherit(self, c)
        assert traits[TRAIT_NAMES.index("armor_p")] == 0.0, "defence code ran with defence off"
        return traits
    monkeypatch.setattr(World, "offspring_traits", checked)
    w = World(Config(width=40, height=20, initial_cells=120, sensing=True, open_genome=True, sex=True,
                     plasticity=True, hgt=True), seed=11)
    for _ in range(300):
        w.step()
    assert w.births > 0 and w.kills > 0 and all(c.armor_p == 0.0 for c in w.cells)
    s = w.stats()
    assert s["defended"] == 0 and s["armor_p_mean"] == 0.0


def test_strong_armour_repels_most_attacks():
    defended = kills = 0
    for seed in range(20):                                        # one prey per world, hunted until eaten
        w = world(seed=seed, defence_strength=0.95, max_age=10**6, div_min=1e3, div_max=1e3)
        hunter_and_prey(w, armor_p=1.0)
        for _ in range(200):
            w.step()
            if w.kills:
                break
        defended, kills = defended + w.defended, kills + w.kills
    assert kills > 0 and defended / (defended + kills) > 0.85    # 95% of attacks fail


def test_a_repelled_attack_moves_no_energy():
    seen = 0
    for seed in range(10):
        w = world(seed=seed, defence_strength=0.95, max_age=10**6, div_min=1e3, div_max=1e3)
        hunter, target = hunter_and_prey(w, armor_p=1.0)
        for _ in range(30):
            before, defended = hunter.energy, w.defended
            w.step()
            if w.kills:
                break
            if w.defended > defended:
                seen += 1
                assert hunter.energy < before                     # only its upkeep was paid
                assert target.alive and w.deaths == 0
    assert seen > 0


def test_neutral_arm_draws_nothing_in_predation():
    """With no cost, the neutral arm must follow the off world draw for draw (cells placed by hand)."""
    states = []
    for kw in ({"defence": False}, {"defence_neutral": True, "defence_upkeep": 0.0}):
        w = world(max_age=10**6, div_min=1e3, div_max=1e3, **kw)
        hunter_and_prey(w, armor_p=1.0 if w.cfg.defence else 0.0)
        for _ in range(30):
            w.step()
        states.append(([(c.id, c.x, c.y, c.energy) for c in w.cells], w.kills, w.rng.getstate()))
    assert states[0][1] > 0 and states[0] == states[1]          # an attack happened, with the same draws


def test_unarmoured_prey_is_always_eaten_when_attacked():
    w = world(max_age=10**6, div_min=1e3, div_max=1e3)
    hunter_and_prey(w, armor_p=0.0)
    for _ in range(40):
        w.step()
        if w.kills:
            break
    assert w.kills == 1 and w.defended == 0


def test_neutral_arm_never_repels():
    w = world(defence_neutral=True, defence_strength=0.95, max_age=10**6, div_min=1e3, div_max=1e3)
    hunter_and_prey(w, armor_p=1.0)
    for _ in range(40):
        w.step()
        if w.kills:
            break
    assert w.kills == 1 and w.defended == 0


def test_upkeep_is_paid_in_both_arms():
    for kw in ({}, {"defence_neutral": True}):
        w = world(defence_upkeep=0.3, **kw)
        c = put(w, 5, 5, [0.5] * N_GENES, armor_p=0.5)
        off = Cell(99, 0, 0, 1.0, [0.5] * N_GENES, 99, Config(width=20, height=20))
        assert c.upkeep == pytest.approx(off.upkeep + 0.15)


def test_armour_is_inherited_with_mutation_and_drawn_at_seeding():
    w = World(Config(width=40, height=20, initial_cells=150, defence=True, immigration_rate=3.0), seed=3)
    assert len({c.armor_p for c in w.cells}) > 100                # drawn per seeded cell
    for _ in range(200):
        w.step()
    kids = [c for c in w.cells if c.id != c.lineage]
    assert w.births > 0 and kids and all(0.0 <= c.armor_p <= 1.0 for c in kids)
    off = World(Config(width=20, height=10, initial_cells=30, immigration_rate=3.0), seed=2)
    off.step()
    assert all(c.armor_p == 0.0 for c in off.cells)


def test_strength_is_bounded_below_immunity():
    with pytest.raises(ValueError):
        Config(defence_strength=1.0).validate()
    Config(defence_strength=0.95).validate()


@pytest.mark.parametrize("extra", [{}, dict(defence_neutral=True),
                                   dict(sex=True, hgt=True, plasticity=True, day_amplitude=1.0, day_length=40)])
def test_defence_runs_resume_bit_exact(tmp_path, extra):
    cfg = Config(width=40, height=20, initial_cells=150, defence=True, **extra)
    straight = World(cfg, seed=4)
    for _ in range(300):
        straight.step()
    first = World(cfg, seed=4)
    for _ in range(150):
        first.step()
    save_world(first, tmp_path / "w.json.gz")
    resumed = load_world(tmp_path / "w.json.gz")
    for _ in range(150):
        resumed.step()

    def key(w):
        return ([(c.id, c.x, c.y, c.energy, tuple(c.genes), c.armor_p) for c in w.cells],
                w.stats(), w.rng.getstate())
    assert key(resumed) == key(straight)
    if not extra:
        assert straight.defended > 0


def test_rejects_invalid_defence_state_in_saves():
    d = world_to_dict(World(Config(width=20, height=10, initial_cells=10, defence=True), seed=1))
    world_from_dict(json.loads(json.dumps(d)))                  # the untouched save loads
    for bad in (1.5, -0.1, float("nan"), True, "x", None):
        e = json.loads(json.dumps(d))
        e["cells"][0][ARMOR_COL] = bad
        with pytest.raises(SaveFormatError):
            world_from_dict(e)
    for bad in (-1, 1.5, True, "3"):
        e = json.loads(json.dumps(d))
        e["counters"]["defended"] = bad
        with pytest.raises(SaveFormatError):
            world_from_dict(e)
    e = json.loads(json.dumps(d))
    e["cells"][0] = e["cells"][0][:ARMOR_COL]                   # a v7-length row
    with pytest.raises(SaveFormatError):
        world_from_dict(e)
    off = world_to_dict(World(Config(width=20, height=10, initial_cells=10), seed=1))
    e = json.loads(json.dumps(off))
    e["cells"][0][ARMOR_COL] = 0.5                              # state present while the flag is off
    with pytest.raises(SaveFormatError):
        world_from_dict(e)
