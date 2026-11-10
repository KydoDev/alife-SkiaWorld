"""Species tracker: pure observer, consistent counts, bounded memory."""
from collections import Counter

from worldsim import Config, World
from worldsim.species import ORIGIN_SPECIATION


def small_config(**overrides):
    cfg = Config(width=40, height=20, initial_cells=80)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def per_cell_history(world, steps):
    out = []
    for _ in range(steps):
        world.step()
        out.append([(c.id, c.x, c.y, c.energy, tuple(b.id for b in c.bonds)) for c in world.cells])
    return out


def test_tracker_does_not_change_the_dynamics():
    on = per_cell_history(World(small_config(), seed=8, track_species=True), 200)
    off = per_cell_history(World(small_config(), seed=8, track_species=False), 200)
    assert on == off


def test_species_threshold_does_not_change_the_dynamics():
    a = per_cell_history(World(small_config(species_threshold=0.1), seed=8), 150)
    b = per_cell_history(World(small_config(species_threshold=0.9), seed=8), 150)
    assert a == b


def test_species_counts_match_living_cells():
    world = World(small_config(), seed=4)
    for _ in range(200):
        world.step()
        actual = Counter(c.species for c in world.cells)
        tracked = {sid: s.count for sid, s in world.tracker.extant.items()}
        assert dict(actual) == tracked
        assert all(s.count > 0 for s in world.tracker.extant.values())


def test_every_retained_species_has_a_retained_ancestry():
    world = World(small_config(), seed=4)
    for _ in range(300):
        world.step()
    species = world.tracker.species
    for s in species.values():
        if s.parent is not None:
            assert s.parent in species, f"species {s.id} lost its parent {s.parent}"
        assert s.children == sum(1 for o in species.values() if o.parent == s.id)


def test_speciation_happens_and_is_bounded_by_threshold():
    loose = World(small_config(species_threshold=10.0), seed=2)   # nothing can speciate
    tight = World(small_config(species_threshold=0.05), seed=2)
    for _ in range(150):
        loose.step()
        tight.step()
    assert loose.tracker.speciations == 0
    assert tight.tracker.speciations > 0
    assert all(s.origin != ORIGIN_SPECIATION for s in loose.tracker.species.values())


def test_failed_immigrant_species_are_pruned():
    world = World(small_config(immigration_rate=2.0), seed=6)
    for _ in range(300):
        world.step()
    t = world.tracker
    assert t.pruned > 0
    # nothing prunable is left behind
    for s in t.species.values():
        assert not (s.extinct is not None and s.children == 0 and s.peak < t.prune_peak and s.established is None)


def test_novelty_counts_only_speciation_born_established_species():
    world = World(small_config(novelty_activity=50), seed=3)
    for _ in range(300):
        world.step()
    t = world.tracker
    expected = sum(1 for s in t.species.values() if s.origin == ORIGIN_SPECIATION and s.established is not None)
    assert t.novelty == expected
