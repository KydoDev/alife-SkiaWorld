"""Static terrain maps (F2): rocks, hydrothermal vents, sunlight per column, initial organic.

A `Terrain` is pure data. It comes either from `generate_terrain` (procedural, from
`Config` and the world seed) or from `worldgen` (an image or a planet form), and it is
stored verbatim in save files so a resumed world never needs the original input.
Procedural generation uses its own RNG, never `World.rng`, so a terrain change never
shifts the random stream of the dynamics.
"""
import math
import random
from dataclasses import dataclass

import numpy as np


@dataclass
class Terrain:
    rock: np.ndarray       # (H, W) bool — tiles no cell can occupy; opaque to light
    chem: np.ndarray       # (H, W) float — chemical energy per step at each tile (vents)
    sun: np.ndarray        # (W,) float — surface light multiplier per column
    organic: np.ndarray    # (H, W) float — initial organic matter

    @classmethod
    def flat(cls, width, height, organic_init=0.0):
        return cls(rock=np.zeros((height, width), dtype=bool),
                   chem=np.zeros((height, width), dtype=np.float64),
                   sun=np.ones(width, dtype=np.float64),
                   organic=np.full((height, width), organic_init, dtype=np.float64))

    @property
    def is_flat(self):
        return not self.rock.any() and not self.chem.any() and bool(np.all(self.sun == 1.0))


def _terrain_rng(seed):
    # A separate, seed-derived stream: same seed -> same terrain, independent of the dynamics.
    return random.Random(f"worldsim-terrain-{seed}")


def seabed_heights(width, height, rock_fraction, rng):
    """Rock height per column: a smooth, x-periodic ridge profile averaging `rock_fraction` * H."""
    if rock_fraction <= 0.0:
        return np.zeros(width, dtype=np.int64)
    x = np.arange(width)
    profile = np.ones(width)
    for k in (1, 2, 3, 5):
        profile += (0.6 / k) * np.sin(2 * math.pi * k * x / width + rng.uniform(0, 2 * math.pi))
    profile = np.clip(profile, 0.0, None)
    profile *= rock_fraction * height / profile.mean()
    # never fill a column to the surface: row 0 stays water
    return np.clip(np.rint(profile), 0, height - 1).astype(np.int64)


def vent_field(rock, vent_count, vent_strength, vent_radius, rng):
    """Chemical energy around `vent_count` vents placed on top of the seabed."""
    H, W = rock.shape
    chem = np.zeros((H, W), dtype=np.float64)
    if vent_count <= 0 or vent_strength <= 0.0:
        return chem
    ys, xs = np.mgrid[0:H, 0:W]
    for _ in range(vent_count):
        vx = rng.randrange(W)
        solid = np.flatnonzero(rock[:, vx])
        vy = (solid[0] if solid.size else H) - 1         # first water tile above the rock
        dx = np.abs(xs - vx)
        dx = np.minimum(dx, W - dx)                       # toroidal in x
        dist = np.hypot(dx, ys - vy)
        chem += vent_strength * np.exp(-dist / vent_radius)
    chem[rock] = 0.0
    return chem


def generate_terrain(cfg, seed) -> Terrain:
    """Procedural terrain from `Config`. Defaults give a flat, vent-free world (v0)."""
    W, H = cfg.width, cfg.height
    terrain = Terrain.flat(W, H, cfg.organic_init)
    if cfg.rock_fraction <= 0.0 and cfg.vent_count <= 0:
        return terrain
    rng = _terrain_rng(seed)
    heights = seabed_heights(W, H, cfg.rock_fraction, rng)
    rows = np.arange(H)[:, None]
    terrain.rock = rows >= (H - heights)[None, :]
    terrain.chem = vent_field(terrain.rock, cfg.vent_count, cfg.vent_strength, cfg.vent_radius, rng)
    terrain.organic[terrain.rock] = 0.0
    return terrain
