"""G2 golden vectors for `genome_distance` (F5a mate choice): CPython's `math.dist` is its own
extended-precision algorithm (`vector_norm`), not a libm call, so the Rust port reproduces it operation by
operation and is checked here against Python on gene pairs, bit for bit (engine-rs/tests/genome_distance.rs).

    python scripts/g2_distance_vectors.py --out engine-rs/tests/genome_distance.json
"""
import argparse
import json
import platform
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worldsim.species import genome_distance  # noqa: E402
from worldsim.world import N_GENES  # noqa: E402


def f64_hex(v: float) -> str:
    return struct.pack("<d", v).hex()


def pairs(seed: int, n: int):
    """Random genomes plus close, sparse and nearly equal partners (the cases near a threshold), and
    tiny or subnormal genes (an untrusted save may hold any value in [0, 1]) for the rescaling branches."""
    rng = random.Random(seed)
    for k in range(n):
        a = [rng.random() for _ in range(N_GENES)]
        mode = k % 7
        if mode == 0:
            b = [rng.random() for _ in range(N_GENES)]
        elif mode == 1:
            b = [min(1.0, max(0.0, v + rng.gauss(0.0, 0.05))) for v in a]
        elif mode == 2:
            b = list(a)
            for i in rng.sample(range(N_GENES), rng.randrange(1, 4)):
                b[i] = rng.random()
        elif mode == 3:
            b = [min(1.0, max(0.0, v + rng.gauss(0.0, 1e-9))) for v in a]
        elif mode == 5:                       # tiny genes against zeros: max down to the smallest subnormal
            e = rng.randrange(1010, 1075)
            a = [rng.random() * 2.0 ** -e for _ in range(N_GENES)]
            b = [0.0 if rng.random() < 0.7 else v for v in a]
        elif mode == 6:                       # mixed magnitudes: large differences next to tiny ones
            b = [v + rng.random() * 2.0 ** -rng.randrange(400, 1075) if rng.random() < 0.8 else rng.random()
                 for v in a]
            b = [min(1.0, v) for v in b]
        else:
            b = list(a)                       # identical: distance 0
        yield a, b


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if platform.python_implementation() != "CPython" or sys.version_info[:2] not in ((3, 12), (3, 13)):
        sys.exit("math.dist must be CPython 3.12/3.13's vector_norm (3.11 uses another algorithm)")
    rows = [{"a": [f64_hex(v) for v in a], "b": [f64_hex(v) for v in b], "d": f64_hex(genome_distance(a, b))}
            for a, b in pairs(args.seed, args.n)]
    doc = {"seed": args.seed, "python": platform.python_version(), "pairs": rows}
    args.out.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{args.out}: {len(rows)} pairs")


if __name__ == "__main__":
    main()
