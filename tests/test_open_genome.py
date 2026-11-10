"""F4 open genome: variable-length rule genes."""
import json
import math

import pytest

from worldsim import Config, World
from worldsim.persistence import SaveFormatError, load_world, save_world, world_from_dict, world_to_dict
from worldsim.world import N_GENES, RULE_CONDITIONS, RULE_DIV, RULE_TARGETS, Cell, decode_rule, describe_rule


def rule(cond, target, intensity, threshold=0.5):
    """Build a rule gene from readable parts (the inverse of decode_rule)."""
    c = (RULE_CONDITIONS.index(cond) + 0.5) / len(RULE_CONDITIONS)
    t = (RULE_TARGETS.index(target) + 0.5) / len(RULE_TARGETS)
    return [c, threshold, t, (intensity + 1.0) / 2.0]


KIN = RULE_TARGETS.index("w_kin")


def world(**kw):
    base = dict(width=20, height=20, initial_cells=0, immigration_rate=0.0, sensing=True, sense_noise=0.0,
                reseed_on_extinction=False, open_genome=True)
    base.update(kw)
    return World(Config(**base), seed=1, track_species=False)   # cells are placed by hand


def put(w, x, y, rules=(), energy=50.0):
    cid = w._new_id()
    c = Cell(cid, x, y, energy, [0.5] * N_GENES, cid, w.cfg, [list(r) for r in rules])
    w._place(c)
    return c


def test_decode_rule_round_trips_the_readable_parts():
    cond, thr, target, w = decode_rule(rule("light<", "w_organic", -0.6, threshold=0.3))
    assert (RULE_CONDITIONS[cond], RULE_TARGETS[target], thr) == ("light<", "w_organic", 0.3)
    assert math.isclose(w, -0.6)
    assert decode_rule([1.0, 1.0, 1.0, 1.0])[0::2] == (len(RULE_CONDITIONS) - 1, RULE_DIV)   # upper edge
    assert describe_rule(rule("always", "div", 0.5)) == "always div +0.50"


def test_off_world_is_unchanged_by_the_feature():
    """With open_genome off, no rule draws happen and the history equals a world that never had F4."""
    cfg = dict(width=40, height=20, initial_cells=120, sensing=True)
    a = World(Config(**cfg), seed=3)
    b = World(Config(**cfg, rule_dup_rate=1.0, rule_new_rate=1.0, rule_upkeep=5.0), seed=3)
    for _ in range(200):
        a.step()
        b.step()
    assert [(c.id, c.x, c.y, c.energy) for c in a.cells] == [(c.id, c.x, c.y, c.energy) for c in b.cells]
    assert all(c.rules == () for c in b.cells)


def test_an_always_rule_steers_like_a_sensor_weight():
    w = world()
    c = put(w, 10, 10, [rule("always", "w_light", 1.0)])
    w.update_light()
    sense, _ = w.rule_effects(c, w.light[10, 10])
    assert sense[0] == pytest.approx(1.0)                     # gene 0.5 = weight 0, plus the rule
    assert w.sensed_move(c, sense)[1] == 9                    # moves up, towards the light


def test_duplicated_rules_add_up_and_conditions_gate_them():
    w = world()
    rules = [rule("always", "w_kin", 0.4), rule("always", "w_kin", 0.4), rule("energy>", "w_kin", 1.0, 0.9)]
    c = put(w, 5, 5, rules, energy=10.0)                      # energy / div_max well below 0.9
    sense, _ = w.rule_effects(c, 0.0)
    assert sense[KIN] == pytest.approx(0.8)
    c.energy = 0.95 * w.cfg.div_max
    sense, _ = w.rule_effects(c, 0.0)
    assert sense[KIN] == pytest.approx(1.8)


def test_light_condition_reads_the_light_at_the_cell():
    w = world()
    c = put(w, 5, 5, [rule("light<", "w_light", 1.0, 0.2)])
    assert w.rule_effects(c, 0.1 * w.cfg.light_max)[0][0] == pytest.approx(1.0)    # dark: active
    assert w.rule_effects(c, 0.9 * w.cfg.light_max)[0][0] == pytest.approx(0.0)    # bright: silent


def test_division_rule_shifts_the_threshold_within_bounds():
    w = world(sensing=False)
    c = put(w, 5, 5, [rule("always", "div", -1.0)])
    _, shift = w.rule_effects(c, 0.0)
    assert shift == pytest.approx(-w.cfg.rule_div_shift * (w.cfg.div_max - w.cfg.div_min))
    c.energy = c.div_thr - 1.0                               # below its genetic threshold ...
    w.step()
    assert w.births == 1                                     # ... but the rule lowers it: it divides


def test_neutral_rules_cost_but_do_nothing():
    on, neutral = world(), world(rules_neutral=True)
    rs = [rule("always", "w_light", 1.0)] * 3
    c_on, c_neutral = put(on, 5, 5, rs), put(neutral, 5, 5, rs)
    assert c_on.upkeep == pytest.approx(c_neutral.upkeep)
    assert c_on.upkeep - put(on, 8, 8).upkeep == pytest.approx(3 * on.cfg.rule_upkeep)
    assert c_on.rule_fx and not c_neutral.rule_fx


def test_rule_mutation_operators_and_cap():
    w = world(rule_dup_rate=1.0, rule_del_rate=0.0, rule_new_rate=0.0, max_rules=3)
    one = [rule("always", "w_light", 0.2)]
    out = w.mutate_rules(one, 0.0)
    assert out == one * 2 and out[0] is not out[1]           # duplication: an independent copy next to it
    assert len(w.mutate_rules(one * 3, 0.0)) == 3            # cap
    w.cfg.rule_dup_rate, w.cfg.rule_new_rate = 0.0, 1.0
    assert len(w.mutate_rules([], 0.0)) == 1                 # de novo source from an empty genome
    w.cfg.rule_new_rate, w.cfg.rule_del_rate = 0.0, 1.0
    assert w.mutate_rules(one, 0.0) == []
    w.cfg.rule_del_rate = 0.0
    assert all(0.0 <= v <= 1.0 for v in w.mutate_rules([[0.0, 1.0, 0.0, 1.0]], 0.5)[0])


def test_rule_genomes_evolve_and_resume_bit_exact(tmp_path):
    cfg = Config(width=40, height=20, initial_cells=150, sensing=True, open_genome=True, rule_new_rate=0.3,
                 day_amplitude=1.0, day_length=40)
    straight = World(cfg, seed=4)
    for _ in range(300):
        straight.step()
    assert straight.stats()["rules_max"] > 0                  # rules appeared
    first = World(cfg, seed=4)
    for _ in range(150):
        first.step()
    save_world(first, tmp_path / "w.json.gz")
    resumed = load_world(tmp_path / "w.json.gz")
    for _ in range(150):
        resumed.step()

    def key(w):
        return [(c.id, c.x, c.y, c.energy, tuple(c.genes), tuple(map(tuple, c.rules))) for c in w.cells], w.stats()
    assert key(resumed) == key(straight)


def test_rejects_hostile_rule_genes():
    cfg = Config(width=20, height=10, initial_cells=10, open_genome=True, max_rules=2)
    d = world_to_dict(World(cfg, seed=1))
    for bad in ([[0.1, 0.2, 0.3]], [[0.1, 0.2, 0.3, 2.0]], [[0.1, 0.2, 0.3, float("nan")]],
                [[0.5] * 4] * 3, "rules", [["a", 0, 0, 0]]):
        e = json.loads(json.dumps(d))
        e["cells"][0][9] = bad
        with pytest.raises(SaveFormatError, match="rule"):
            world_from_dict(e)
    off = world_to_dict(World(Config(width=20, height=10, initial_cells=10), seed=1))
    off["cells"][0][9] = [[0.5] * 4]                          # rules in a world without the open genome
    with pytest.raises(SaveFormatError, match="rule"):
        world_from_dict(off)


@pytest.mark.parametrize("field, value", [("rule_dup_rate", 1.5), ("max_rules", 65), ("rule_upkeep", -1.0),
                                          ("rule_div_shift", 2.0)])
def test_rule_parameters_are_bounded(field, value):
    with pytest.raises(ValueError):
        Config(**{field: value}).validate()


def test_stats_report_rule_counts():
    w = world()
    put(w, 1, 1, [rule("always", "div", 0.1)] * 2)
    put(w, 3, 3)
    s = w.stats()
    assert (s["rules_mean"], s["rules_max"]) == (1.0, 2)


def test_malformed_saves_raise_save_format_error():
    cfg = Config(width=20, height=10, initial_cells=10, open_genome=True)
    d = world_to_dict(World(cfg, seed=1))
    cases = []
    short = json.loads(json.dumps(d))
    short["cells"][0] = short["cells"][0][:9]                 # a v3-shaped row
    cases.append(short)
    huge = json.loads(json.dumps(d))
    huge["cells"][0][9] = [[0.5, 0.5, 0.5, 10 ** 400]]         # valid JSON, overflows a float
    cases.append(huge)
    huge_gene = json.loads(json.dumps(d))
    huge_gene["cells"][0][5][0] = 10 ** 400
    cases.append(huge_gene)
    boolean = json.loads(json.dumps(d))
    boolean["cells"][0][9] = [[True, 0.5, 0.5, 0.5]]
    cases.append(boolean)
    no_rng = json.loads(json.dumps(d))
    no_rng["rng"] = {"internal": "x"}
    cases.append(no_rng)
    for e in cases:
        with pytest.raises(SaveFormatError):
            world_from_dict(e)


def test_division_shift_is_clamped_at_div_max():
    w = world(sensing=False, rule_div_shift=1.0)
    put(w, 5, 5, [rule("always", "div", 1.0)] * 4, energy=w.cfg.div_max + 1.0)
    w.step()
    assert w.births == 1                                     # threshold clamped to div_max, not beyond


def test_child_rules_are_independent_of_the_parent():
    w = world(sensing=False, rule_dup_rate=1.0)
    parent = put(w, 5, 5, [rule("always", "w_light", 0.0)], energy=w.cfg.div_max + 5.0)
    before = [list(r) for r in parent.rules]
    w.step()
    child = next(c for c in w.cells if c is not parent)
    assert parent.rules == before
    assert len(child.rules) == 2 and all(r is not p for r in child.rules for p in parent.rules)


def test_cap_holds_when_duplication_and_insertion_both_fire():
    w = world(rule_dup_rate=1.0, rule_new_rate=1.0, max_rules=2)
    assert len(w.mutate_rules([rule("always", "w_kin", 0.1)], 0.0)) == 2
    assert len(w.mutate_rules([rule("always", "w_kin", 0.1)] * 2, 0.0)) == 2


def test_off_world_never_runs_rule_code(monkeypatch):
    """With open_genome off no rule code runs, so it cannot draw random numbers or reorder anything: the
    world stays the F3 engine. (Checked once against the F3 commit itself by fingerprint, on one platform;
    float results differ across platforms, so that fingerprint is not a CI test.)"""
    def boom(*_):
        raise AssertionError("rule code ran with the open genome off")
    monkeypatch.setattr(World, "rule_effects", boom)
    monkeypatch.setattr(World, "mutate_rules", boom)
    w = World(Config(width=40, height=20, initial_cells=120, sensing=True, day_amplitude=1.0, day_length=40,
                     vent_count=2, rock_fraction=0.1), seed=11)
    for _ in range(300):
        w.step()
    assert w.births > 0 and all(c.rules == () and c.rule_fx == () for c in w.cells)
