"""Simulation parameters. Everything tunable lives here."""
from dataclasses import dataclass, asdict


@dataclass
class Config:
    # --- world ---
    width: int = 160
    height: int = 64
    initial_cells: int = 400
    initial_energy: float = 40.0

    # --- light ---
    light_max: float = 1.0          # light at the surface
    light_depth: float = 30.0       # attenuation length with depth (rows)
    shade: float = 0.7              # light transmitted by each cell above

    # --- organic matter ---
    organic_init: float = 0.0
    organic_diffusion: float = 0.10  # fraction exchanged with neighbors per step
    organic_sink: float = 0.01       # fraction sinking one row per step
    organic_decay: float = 0.002     # fraction lost per step
    decomp_fraction: float = 0.9     # share of (energy + body) that becomes organic matter at death

    # --- metabolism ---
    base_cost: float = 0.20
    pred_upkeep: float = 0.30        # fixed cost of being a predator (x pred)
    move_upkeep: float = 0.10        # fixed cost of motility (x move gene)
    move_cost: float = 0.20          # cost of each move
    spec_exp: float = 2.0            # specialization exponent (>1 rewards specialists)

    # --- feeding ---
    photo_gain: float = 3.0
    sapro_rate: float = 1.0          # max organic matter absorbed per step
    sapro_eff: float = 0.8
    pred_eff: float = 0.5

    # --- reproduction ---
    body_cost: float = 5.0           # energy to build a body (returned at death)
    div_min: float = 10.0
    div_max: float = 60.0
    max_age: int = 600
    max_bonds: int = 8

    # --- mutation ---
    mut_min: float = 0.005
    mut_max: float = 0.15

    # --- immigration (random cells appear: keeps diversity up) ---
    immigration_rate: float = 0.5    # new cells per step (e.g. 0.5 = one every 2 steps)

    # --- safety ---
    reseed_on_extinction: bool = True

    def to_dict(self):
        return asdict(self)
