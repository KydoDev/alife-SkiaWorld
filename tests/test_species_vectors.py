"""scripts/g3_species_vectors.py (G3 P8, ADR-0018): the species golden file and the tracked start save are what
species.py gives, the cases are not vacuous, and the digests follow their documented layout."""
import gzip
import hashlib
import importlib.util
import json
import platform
import struct
from pathlib import Path

import pytest

from worldsim.config import Config
from worldsim.persistence import load_world
from worldsim.world import World

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "engine-rs" / "tests" / "golden"


def _module():
    spec = importlib.util.spec_from_file_location("g3_species_vectors", ROOT / "scripts" / "g3_species_vectors.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def committed():
    return json.loads((GOLDEN / "species.json").read_text(encoding="utf-8"))


def _off_os(request, committed):
    if platform.system() != committed["system"]:
        request.applymarker(pytest.mark.xfail(strict=False, reason=f"made on {committed['system']}; libm may differ"))


def test_committed_species_vectors_match_this_python(request, committed, tmp_path):
    """Regenerated into a scratch root (the generator writes the start save there): same cases, same save."""
    _off_os(request, committed)
    sv = _module()
    assert committed["cases"] == sv.build(tmp_path)["cases"], "regenerate species.json"
    assert (tmp_path / sv.START_SAVE).read_bytes() == (GOLDEN / sv.START_SAVE).read_bytes(), "regenerate the save"


def test_the_start_save_carries_a_tracker_and_is_byte_stable(committed):
    sv = _module()
    assert sv.start_save_bytes() == sv.start_save_bytes(), "gzip with mtime 0: no timestamp in the bytes"
    world = load_world(GOLDEN / committed["start_save"])
    assert world.tracker is not None and world.step_count == sv.SAVE_STEPS
    assert all(c.species in world.tracker.extant for c in world.cells)


def test_the_tracker_digest_follows_its_layout():
    """The documented byte layout, rebuilt by hand on a small tracked world (the kernel computes the same bytes)."""
    sv = _module()
    w = World(Config(width=8, height=8, initial_cells=6), seed=2)
    for _ in range(40):
        w.step()
    t = w.tracker
    h = hashlib.sha256(struct.pack("<QQQQ", t.next_id, t.speciations, t.novelty, t.pruned))
    for sid in sorted(t.species):
        s = t.species[sid]
        for v in (s.id, s.parent or 0, sv.ORIGINS.index(s.origin), s.born,
                  2**64 - 1 if s.extinct is None else s.extinct, s.count, s.peak, s.activity,
                  2**64 - 1 if s.established is None else s.established, s.children):
            h.update(struct.pack("<Q", v))
        for g in s.founder_genes:
            h.update(struct.pack("<d", g))
    assert sv.tracker_digest(t) == h.hexdigest()
    cells = hashlib.sha256(b"".join(struct.pack("<QQ", c.id, c.species) for c in sorted(w.cells, key=lambda c: c.id)))
    assert sv.cells_digest(w) == cells.hexdigest()


def test_the_final_dump_matches_the_last_digest(committed):
    """The full dump at the end is the state the last sample's digest was taken on (a kernel can diff either)."""
    sv = _module()
    for case in committed["cases"]:
        d = case["tracker"]
        h = hashlib.sha256(struct.pack("<4Q", d["next_id"], d["speciations"], d["novelty"], d["pruned"]))
        for row in d["species"]:
            sid, parent, origin, genes, born, extinct, count, peak, activity, established, children = row
            h.update(struct.pack("<10Q", sid, parent or 0, sv.ORIGINS.index(origin), born,
                                 2**64 - 1 if extinct is None else extinct, count, peak, activity,
                                 2**64 - 1 if established is None else established, children))
            h.update(b"".join(bytes.fromhex(g) for g in genes))     # f64_hex: the little-endian bytes
        assert h.hexdigest() == case["samples"][-1]["tracker"], case["name"]
        cells = hashlib.sha256(b"".join(struct.pack("<QQ", i, s) for i, s in case["cells"]))
        assert cells.hexdigest() == case["samples"][-1]["cells"], case["name"]


def test_the_generator_refuses_vacuous_cases(committed):
    sv = _module()
    sv.check_not_vacuous(committed["cases"])
    emptied = (("speciations", "no speciation"), ("novelty", "no established"), ("pruned", "no species pruned"))
    for key, match in emptied:
        cases = json.loads(json.dumps(committed["cases"]))
        for c in cases:
            c["tracker"][key] = 0
        with pytest.raises(AssertionError, match=match):
            sv.check_not_vacuous(cases)
    cases = json.loads(json.dumps(committed["cases"]))
    for c in cases:
        c["facts"]["killed_by_action"] = 0
    with pytest.raises(AssertionError, match="intervention"):
        sv.check_not_vacuous(cases)
    cases = json.loads(json.dumps(committed["cases"]))
    for c in cases:
        c["facts"]["reseeds"] = 0
    with pytest.raises(AssertionError, match="reseed"):
        sv.check_not_vacuous(cases)


def test_tracking_never_changes_the_history():
    """ADR-0003, as the generator asserts on every sample: the twin without a tracker has the same hashes."""
    sv = _module()
    g2 = sv._golden_module()
    a, b = World(Config(), seed=5), World(Config(), seed=5, track_species=False)
    for _ in range(60):
        a.step()
        b.step()
    assert g2.state_hash(a) == g2.state_hash(b)


def test_the_save_is_gzip_without_a_timestamp():
    data = _module().start_save_bytes()
    assert data[4:8] == b"\0\0\0\0", "gzip MTIME field must be 0"
    assert json.loads(gzip.decompress(data))["tracker"] is not None
