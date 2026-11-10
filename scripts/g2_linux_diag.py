"""Throwaway G2 diagnostic (not to be merged): do numpy's power/exp agree with libm here?"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from worldsim.persistence import load_world  # noqa: E402

for name in ("default", "volcanic"):
    w = load_world(Path("engine-rs/target/golden-linux") / name / "start.json.gz")
    cfg, H, W = w.cfg, w.H, w.W
    rows = np.arange(H, dtype=np.float64)
    ne = np.exp(-rows / cfg.light_depth)
    me = [math.exp(v) for v in (-rows / cfg.light_depth)]
    bad_e = [y for y in range(H) if ne[y] != me[y]]
    above = np.tile(rows[:, None], (1, W))          # same shape/layout as update_light
    npw = np.power(cfg.shade, above)
    bad_p = sorted({int(k) for k in range(H) if (npw[k] != math.pow(cfg.shade, float(k))).any()})
    print(f"{name}: shade={cfg.shade} light_depth={cfg.light_depth} H={H}")
    print(f"  np.exp != math.exp at rows {bad_e}")
    print(f"  np.power(shade, k) != math.pow at k {bad_p}")
