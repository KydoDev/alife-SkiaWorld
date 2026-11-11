"""G2 golden vectors for numpy's `ndarray.mean()` (ADR-0012 piece 2): terrain generation divides by
`profile.mean()`, numpy's pairwise summation, which the kernel reproduces. The data of each length is drawn
from `random.Random(SEED_BASE + n)` with `+` and `*` only (exact in IEEE), so the kernel rebuilds it from its
own seeded generator and the file holds only the results; checked by engine-rs/tests/numpy_mean.rs.

    python scripts/g2_mean_vectors.py --out engine-rs/tests/mean_vectors.json
"""
import argparse
import json
import platform
import random
import struct
from pathlib import Path

import numpy as np

SEED_BASE = 1000
# around numpy's blocks: 8 accumulators, blocks of 128, pairwise split above; 8192 = the ufunc buffer size;
# 10 000 = the largest width
LENGTHS = [*range(1, 21), *range(127, 131), *range(255, 258), *range(1023, 1026), *range(8191, 8194), 10_000]


def data(n: int) -> list[float]:
    rng = random.Random(SEED_BASE + n)
    return [rng.random() * rng.random() * 1000.0 + rng.random() for _ in range(n)]


def f64_hex(v: float) -> str:
    return struct.pack("<d", v).hex()


def case(n: int) -> dict:
    arr = np.array(data(n), dtype=np.float64)
    return {"n": n, "sum": f64_hex(float(arr.sum())), "mean": f64_hex(float(arr.mean()))}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    doc = {"numpy": np.__version__, "python": platform.python_version(), "seed_base": SEED_BASE,
           "cases": [case(n) for n in LENGTHS]}
    args.out.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{args.out}: {len(LENGTHS)} lengths")


if __name__ == "__main__":
    main()
