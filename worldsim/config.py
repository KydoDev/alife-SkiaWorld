"""Simulation parameters. Everything tunable lives here."""
import math
from dataclasses import asdict, dataclass, fields

MAX_WORLD_TILES = 1_000_000      # width * height cap for any world, including untrusted inputs

# Bounds enforced by `Config.validate()` (inclusive). Fields not listed must be finite and >= 0.
_BOUNDS = {
    "width": (2, 10_000), "height": (2, 10_000),
    "light_depth": (1e-6, math.inf), "vent_radius": (1e-6, math.inf),
    "day_length": (1, 10**9), "year_length": (1, 10**9),
    "shade": (0, 1), "day_amplitude": (0, 1), "season_amplitude": (0, 1),
    "organic_diffusion": (0, 1), "organic_sink": (0, 1), "organic_decay": (0, 1),
    "decomp_fraction": (0, 1), "sapro_eff": (0, 1), "pred_eff": (0, 1),
    "rock_fraction": (0, 0.9), "vent_count": (0, 100), "max_bonds": (0, 8),
    "max_age": (1, 10**9), "mut_min": (0, 1), "mut_max": (0, 1),
    "immigration_rate": (0, 100), "species_threshold": (1e-9, math.inf),
    "novelty_activity": (1, 10**12), "sense_noise": (0, 10), "sense_upkeep": (0, 10),
    "rule_dup_rate": (0, 1), "rule_del_rate": (0, 1), "rule_new_rate": (0, 1), "rule_upkeep": (0, 10),
    "max_rules": (0, 64), "rule_div_shift": (0, 1),
    "mate_radius": (1, 5), "mate_distance": (0, 10), "sex_cost": (0, 10),
    "plastic_rate": (0, 1), "plastic_upkeep": (0, 10),
    "hgt_rate": (0, 1), "hgt_upkeep": (0, 10),
}


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
    # light cycles (F2): factor = (1 + day_amp*sin(2*pi*t/day)) * (1 + season_amp*sin(2*pi*t/year)).
    # Mean-preserving, so a cycle changes the variability of light, not its average.
    day_length: int = 200           # steps per day/night cycle
    day_amplitude: float = 0.0      # 0 = constant light, 1 = pitch-dark midnight
    year_length: int = 4000         # steps per year
    season_amplitude: float = 0.0   # 0 = no seasons; 0.5 = winter gets half the mean light

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
    chemo_gain: float = 3.0          # energy per step from chemosynthesis at chem = 1 (vents)

    # --- terrain (F2; procedural, from its own seed-derived RNG). Defaults = flat v0 world ---
    rock_fraction: float = 0.0       # mean seabed rock height, as a fraction of the world height
    vent_count: int = 0              # hydrothermal vents on top of the seabed
    vent_strength: float = 2.0       # chemical energy at a vent mouth (1.0 was below the colonisation threshold)
    vent_radius: float = 4.0         # e-folding distance of the chemical field (tiles)

    # --- sensing and behaviour (F3). Off by default: movement stays a random walk ---
    sensing: bool = False            # directed movement steered by the 6 sensor genes (weights in [-1, 1])
    sense_noise: float = 0.1         # random jitter added to each candidate tile's score (breaks ties)
    sense_upkeep: float = 0.05       # cost per step x mean |sensor weight|, paid only when sensing is on

    # --- open genome (F4). Off by default: cells carry no rule genes ---
    open_genome: bool = False        # variable-length list of rule genes (condition -> target, intensity)
    rules_neutral: bool = False      # control arm: rules mutate and cost the same but have no effect
    rule_dup_rate: float = 0.02      # per division: duplicate one rule (the copy sits next to it)
    rule_del_rate: float = 0.02      # per division: delete one rule
    rule_new_rate: float = 0.01      # per division: add a random new rule (de novo source)
    rule_upkeep: float = 0.01        # cost per rule per step
    max_rules: int = 16              # hard cap on the number of rules per cell
    rule_div_shift: float = 0.5      # a division rule shifts the threshold by intensity x this x (div_max - div_min)

    # --- two parents (F5a). Off by default: division is asexual ---
    sex: bool = False                # cells carry an evolvable propensity sex_p to recombine with a partner
    sex_neutral: bool = False        # control arm: sex_p is inherited and mutates, but mating never happens
    mate_radius: int = 2             # partners are searched within this Chebyshev distance
    mate_distance: float = 0.3       # max fixed-gene distance to a partner (own field, not the species threshold)
    sex_cost: float = 0.0            # energy the dividing cell pays each time it mates

    # --- plasticity (F5b). Off by default: the diet is fixed by the genes for life ---
    plasticity: bool = False         # cells carry an evolvable rate plast_p of within-life diet acclimation
    plastic_neutral: bool = False    # control arm: plast_p is inherited and mutates, but the diet never moves
    plastic_rate: float = 0.05       # per-step acclimation at plast_p = 1 (time constant >= 1 / rate steps)
    plastic_upkeep: float = 0.05     # cost per step x plast_p (paid in the neutral arm too)

    # --- horizontal gene transfer (F5c). Off by default: genes change only at division ---
    hgt: bool = False                # cells carry an evolvable propensity hgt_p to copy a neighbour's gene
    hgt_neutral: bool = False        # control arm: hgt_p is inherited and mutates, but no gene is copied
    hgt_rate: float = 0.1            # per-step chance of a transfer at hgt_p = 1
    hgt_upkeep: float = 0.05         # cost per step x hgt_p (paid in the neutral arm too)

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

    # --- observation (species tracking; never read by the dynamics) ---
    species_threshold: float = 0.3   # genome distance from the founder that starts a new species
    novelty_activity: int = 1000     # population-steps after which a species counts as established
    species_prune_peak: int = 5      # extinct childless species below this peak size are forgotten

    # --- safety ---
    reseed_on_extinction: bool = True

    def to_dict(self):
        return asdict(self)

    def apply_overrides(self, assignments) -> "Config":
        """Apply `KEY=VALUE` strings (CLI `--set`); the type is inferred from the default."""
        types = {f.name: type(f.default) for f in fields(self)}
        for kv in assignments:
            key, sep, value = kv.partition("=")
            if not sep or key not in types:
                raise ValueError(f"unknown parameter or missing '=': {kv!r}")
            kind = types[key]
            try:
                setattr(self, key, value.lower() in ("1", "true", "yes") if kind is bool else kind(value))
            except ValueError as e:
                raise ValueError(f"{key} must be {kind.__name__}: {value!r}") from e
        return self

    def validate(self) -> "Config":
        """Check types and ranges (configs can come from untrusted saves and planet forms).

        Ints given for float fields are converted. Raises ValueError with a readable message."""
        for f in fields(self):
            v, kind = getattr(self, f.name), type(f.default)
            if kind is float and isinstance(v, int) and not isinstance(v, bool):
                v = float(v)
                setattr(self, f.name, v)
            if not isinstance(v, kind) or (isinstance(v, bool) and kind is not bool):
                raise ValueError(f"config {f.name} must be {kind.__name__}, got {type(v).__name__}")
            if kind is bool:
                continue
            lo, hi = _BOUNDS.get(f.name, (0, math.inf))
            if not (math.isfinite(v) and lo <= v <= hi):
                raise ValueError(f"config {f.name} = {v!r} is outside [{lo}, {hi}]")
        if self.width * self.height > MAX_WORLD_TILES:
            raise ValueError(f"world size {self.width}x{self.height} exceeds {MAX_WORLD_TILES} tiles")
        if self.initial_cells > self.width * self.height:
            raise ValueError("initial_cells exceeds the number of tiles")
        if self.div_min > self.div_max or self.mut_min > self.mut_max:
            raise ValueError("div_min/mut_min must not exceed div_max/mut_max")
        return self
