"""G2 golden vectors for seeding (ADR-0012 piece 1): CPython's `random.Random(seed)` for the integer and
string seeds the kernel ports, as the full generator state plus a digest of the first 1000 `random()` draws,
checked bit for bit by engine-rs/tests/seed_vectors.rs.

    python scripts/g2_seed_vectors.py --out engine-rs/tests/seed_vectors.json
"""
import argparse
import hashlib
import json
import platform
import random
import struct
import sys
from pathlib import Path

INT_SEEDS = [0, 1, 42, 2**31 - 1, 2**32 - 1, 2**32, 2**63, 2**64 - 1]
# the terrain stream's seed strings (terrain._terrain_rng), plus empty and non-ASCII strings
STR_SEEDS = [f"worldsim-terrain-{s}" for s in (0, 42, 2**64 - 1)] + ["", "é-ü-水"]
DRAWS = 1000


def case(kind: str, seed) -> dict:
    rng = random.Random(seed)
    _, internal, gauss_next = rng.getstate()
    assert gauss_next is None
    draws = b"".join(struct.pack("<d", rng.random()) for _ in range(DRAWS))
    return {"kind": kind, "seed": str(seed), "state": list(internal),
            "draws_sha256": hashlib.sha256(draws).hexdigest()}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if platform.python_implementation() != "CPython":
        sys.exit("the reference is CPython's random module")
    cases = [case("int", s) for s in INT_SEEDS] + [case("str", s) for s in STR_SEEDS]
    doc = {"python": platform.python_version(), "draws": DRAWS, "cases": cases}
    args.out.write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{args.out}: {len(cases)} seeds")


if __name__ == "__main__":
    main()
