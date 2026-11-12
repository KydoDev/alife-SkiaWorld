"""The trait table (ADR-0014): one list drives the per-cell values outside the genome, in a fixed order."""
import random

import pytest

from worldsim import Config, World
from worldsim.world import N_GENES, NO_TRAITS, TRAIT_NAMES, TRAITS, Cell, make_traits


def test_the_table_order_is_the_rng_order_and_new_traits_are_appended():
    # the draw order of founders and children is part of every saved RNG stream: it may only grow at the end
    assert TRAIT_NAMES[:4] == ("sex_p", "plast_p", "hgt_p", "armor_p")
    cfg = Config()
    for t in TRAITS:
        assert isinstance(getattr(cfg, t.flag), bool)
        assert t.upkeep is None or isinstance(getattr(cfg, t.upkeep), float)


def test_make_traits_names_values_and_refuses_unknown_ones():
    assert make_traits() == NO_TRAITS
    traits = make_traits(hgt_p=0.25, armor_p=1)
    assert traits[TRAIT_NAMES.index("hgt_p")] == 0.25 and traits[TRAIT_NAMES.index("armor_p")] == 1.0
    with pytest.raises(ValueError, match="unknown traits"):
        make_traits(armour=0.5)


def test_a_cell_holds_each_value_in_its_named_slot():
    values = tuple(0.1 * (i + 1) for i in range(len(TRAITS)))
    c = Cell(1, 0, 0, 1.0, [0.5] * N_GENES, 1, Config(), traits=values)
    assert tuple(getattr(c, name) for name in TRAIT_NAMES) == values


def test_founders_draw_one_value_per_trait_that_is_on_in_table_order():
    w = World(Config(width=8, height=8, initial_cells=0, plasticity=True, defence=True), seed=3)
    state = w.rng.getstate()
    traits = w.founder_traits()
    rng = random.Random()
    rng.setstate(state)
    assert traits == make_traits(plast_p=rng.random(), armor_p=rng.random())


def test_children_inherit_mutated_values_and_skip_the_traits_that_are_off():
    w = World(Config(width=8, height=8, initial_cells=0, sex=True, hgt=True), seed=3)
    parent = Cell(1, 0, 0, 1.0, [0.5] * N_GENES, 1, w.cfg, traits=make_traits(sex_p=0.4, hgt_p=0.6))
    state = w.rng.getstate()
    traits = w.offspring_traits(parent)
    rng = random.Random()
    rng.setstate(state)
    sigma = parent.mut_sigma
    expect = make_traits(sex_p=min(1.0, max(0.0, 0.4 + rng.gauss(0.0, sigma))),
                         hgt_p=min(1.0, max(0.0, 0.6 + rng.gauss(0.0, sigma))))
    assert traits == expect
    assert w.rng.getstate() == rng.getstate()          # exactly two draws: none for the traits that are off


def test_stats_report_every_trait_mean_also_for_an_empty_world():
    w = World(Config(width=8, height=8, initial_cells=0, reseed_on_extinction=False), seed=3)
    s = w.stats()
    assert all(s[name + "_mean"] == 0.0 for name in TRAIT_NAMES)
    assert s["rules_max"] == 0 and s["diet_shift"] == 0.0
    w = World(Config(width=8, height=8, initial_cells=20, defence=True), seed=3)
    s = w.stats()
    assert s["armor_p_mean"] > 0.0 and s["sex_p_mean"] == 0.0
