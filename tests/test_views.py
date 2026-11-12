"""worldsim/views.py: the ABI 4 views (ADR-0016) are read-only and pack what the front-end needs."""
import math
import struct

import pytest

from worldsim.config import Config
from worldsim.views import (KIND_CHEMO, KIND_EMPTY, KIND_PHOTO, KIND_PRED, KIND_SAPRO, cell_record, chem_level,
                            colony_size, energy_level, energy_level_of, kind, tile_word, tile_words)
from worldsim.world import World


class FakeCell:
    def __init__(self, photo=0.0, sapro=0.0, pred=0.0, chemo=0.0, energy=10.0, div_thr=20.0):
        self.photo, self.sapro, self.pred, self.chemo = photo, sapro, pred, chemo
        self.energy, self.div_thr = energy, div_thr


def _world(seed=3, steps=30, **kw):
    w = World(Config(**kw), seed=seed)
    for _ in range(steps):
        w.step()
    return w


def test_kind_follows_strategy_and_the_first_wins_a_tie():
    assert kind(FakeCell(photo=0.5, sapro=0.2)) == KIND_PHOTO
    assert kind(FakeCell(sapro=0.6)) == KIND_SAPRO
    assert kind(FakeCell(pred=0.4, chemo=0.3)) == KIND_PRED
    assert kind(FakeCell(chemo=0.9)) == KIND_CHEMO
    assert kind(FakeCell(photo=0.3, sapro=0.3, pred=0.3)) == KIND_PHOTO
    assert kind(FakeCell(sapro=0.4, chemo=0.4)) == KIND_SAPRO


def test_energy_level_is_clamped_and_nan_safe():
    assert energy_level(FakeCell(energy=0.0)) == 0
    assert energy_level(FakeCell(energy=10.0, div_thr=20.0)) == 8
    assert energy_level(FakeCell(energy=19.99, div_thr=20.0)) == 15
    assert energy_level(FakeCell(energy=500.0)) == 15
    assert energy_level(FakeCell(energy=-3.0)) == 0
    assert energy_level(FakeCell(energy=math.nan)) == 0


def test_chem_level_clips_like_the_render():
    assert [chem_level(c) for c in (-1.0, 0.0, 0.24, 0.25, 0.5, 0.99, 1.0, 7.0)] == [0, 0, 0, 1, 2, 3, 3, 3]


def test_words_pack_each_field_in_its_own_byte():
    w = _world(rock_fraction=0.2, vent_count=4)
    words = tile_words(w)
    assert len(words) == w.W * w.H * 4
    rock_seen = chem_seen = False
    for y in range(w.H):
        for x in range(w.W):
            word = struct.unpack_from("<I", words, (y * w.W + x) * 4)[0]
            assert word == tile_word(w, x, y)
            assert word & 0x80 == 0 and word & 0xF000 == 0, "reserved bits stay 0"
            assert bool(word & 0x10) == bool(w.terrain.rock[y, x])
            rock_seen |= bool(word & 0x10)
            chem_seen |= bool(word & 0x60)
            c = w.grid[y * w.W + x]
            if c is None:
                assert word & 0x7 == KIND_EMPTY and word >> 16 == 0 and word & 0xF08 == 0
            else:
                assert word & 0x7 == kind(c)
                assert bool(word & 0x8) == bool(c.bonds)
                assert (word >> 8) & 0xF == energy_level(c)
                assert word >> 16 == c.lineage % 65536
    assert rock_seen and chem_seen


def test_cell_record_and_colony_size():
    w = _world(steps=60)
    bonded = [c for c in w.cells if c.bonds]
    assert bonded, "the default world forms colonies by step 60"
    c = bonded[0]
    r = cell_record(w, c.x, c.y)
    assert r["present"] == 1 and r["id"] == c.id and r["lineage"] == c.lineage and r["age"] == c.age
    assert r["energy"] == c.energy and r["genes"] == list(c.genes) and len(r["traits"]) == 5
    assert r["shares"] == [c.photo, c.sapro, c.pred, c.chemo]
    assert r["bonds"] == len(c.bonds) and r["colony"] == colony_size(c) >= 2
    # the component is symmetric: every member reports the same size
    assert all(colony_size(b) == r["colony"] for b in c.bonds)
    lone = next(c for c in w.cells if not c.bonds)
    assert cell_record(w, lone.x, lone.y)["colony"] == 1


def test_an_empty_tile_is_not_present_and_outside_is_refused():
    w = _world()
    x, y = next((i % w.W, i // w.W) for i, c in enumerate(w.grid) if c is None)
    r = cell_record(w, x, y)
    assert r["present"] == 0 and r["colony"] == 0 and r["genes"] == [0.0] * 16
    for x, y in ((-1, 0), (w.W, 0), (0, w.H)):
        with pytest.raises(ValueError):
            cell_record(w, x, y)


def test_views_change_nothing():
    """Read-only: the state after the views is the state before (same next steps, same RNG)."""
    a, b = _world(seed=9, steps=20), _world(seed=9, steps=20)
    tile_words(a)
    for c in list(a.cells)[:10]:
        cell_record(a, c.x, c.y)
    for _ in range(5):
        a.step()
        b.step()
    assert a.rng.getstate() == b.rng.getstate()
    assert [(c.id, c.x, c.y, c.energy) for c in a.cells] == [(c.id, c.x, c.y, c.energy) for c in b.cells]


def test_edge_values_match_the_kernels_rules():
    """NaN and infinities take the documented values (the kernel's `views.rs` mirrors these branches)."""
    assert energy_level(FakeCell(energy=math.inf)) == 15
    assert energy_level(FakeCell(energy=-math.inf)) == 0
    assert chem_level(math.nan) == 0 and chem_level(math.inf) == 3 and chem_level(0.7499) == 2
    # a zero division threshold (div_min = 0, gene 0) divides as IEEE-754 does, like the kernel
    assert [energy_level_of(e, 0.0) for e in (5.0, 0.0, -5.0, math.nan)] == [15, 0, 0, 0]
    assert energy_level_of(-0.0, 20.0) == 0 and energy_level_of(math.inf, math.inf) == 0


def test_a_zero_division_threshold_does_not_raise():
    w = _world(steps=3, div_min=0.0, div_max=0.0)
    assert len(tile_words(w)) == w.W * w.H * 4


def test_the_vector_script_records_what_the_kernel_compares(tmp_path, request):
    """scripts/g3_view_vectors.py: per set two snapshots whose state hash is the golden one at that step.
    The stepped hash depends on libm, so it is expected only on the OS the golden steps were made on."""
    import csv
    import importlib.util
    import json
    import platform
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    rng_golden = root / "engine-rs/tests/golden/default/rng.json"
    made_on = json.loads(rng_golden.read_text(encoding="utf-8"))["meta"]["system"]
    if platform.system() != made_on:
        request.applymarker(pytest.mark.xfail(strict=False, reason=f"golden steps made on {made_on}; maths may differ"))
    spec = importlib.util.spec_from_file_location("g3v", root / "scripts" / "g3_view_vectors.py")
    g3v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g3v)
    g3v.SETS = ("default",)    # this module instance only
    out = tmp_path / "views.json"
    g3v.write(root / "engine-rs" / "tests" / "golden", out)
    doc = json.loads(out.read_text(encoding="utf-8"))
    snaps = doc["cases"][0]["snapshots"]
    hashes = (root / "engine-rs/tests/golden/default/hashes.csv").read_text(encoding="utf-8").splitlines()
    rows = {r["step"]: r["hash"] for r in csv.DictReader(hashes)}
    assert [rows[str(s["step"])] for s in snaps] == [s["state_hash"] for s in snaps]
    assert 0 < len(snaps[1]["cells"]) <= g3v.MAX_CELLS


def test_committed_view_vectors_match_this_python(request):
    """engine-rs/tests/golden/views.json holds, on the OS it was made on, exactly what this Python writes."""
    import importlib.util
    import json
    import platform
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("g3v", root / "scripts" / "g3_view_vectors.py")
    g3v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g3v)
    committed = json.loads((root / "engine-rs/tests/golden/views.json").read_text(encoding="utf-8"))
    if platform.system() != committed["system"]:
        request.applymarker(pytest.mark.xfail(strict=False, reason=f"made on {committed['system']}; libm may differ"))
    assert committed == g3v.build(root / "engine-rs" / "tests" / "golden"), "regenerate views.json"


def test_the_key_wraps_and_the_top_byte_is_used():
    """lineage >= 2**16 wraps; a key with its top bit set fills byte 3 (the C# unpacker must not sign-extend)."""
    w = _world(steps=0)
    c = w.cells[0]
    c.lineage = 70000
    assert tile_word(w, c.x, c.y) >> 16 == 70000 - 65536
    c.lineage = 0xFFFF
    assert tile_word(w, c.x, c.y) >> 24 == 0xFF
