"""Parametri della simulazione. Tutto ciò che si tara sta qui."""
from dataclasses import dataclass, asdict


@dataclass
class Config:
    # --- mondo ---
    width: int = 160
    height: int = 64
    initial_cells: int = 400
    initial_energy: float = 40.0

    # --- luce ---
    light_max: float = 1.0          # luce in superficie
    light_depth: float = 30.0       # scala di attenuazione con la profondità (righe)
    shade: float = 0.7              # luce trasmessa da ogni cellula sopra

    # --- materia organica ---
    organic_init: float = 0.0
    organic_diffusion: float = 0.10  # frazione scambiata con le vicine per passo
    organic_sink: float = 0.01       # frazione che scende di una riga per passo
    organic_decay: float = 0.002     # frazione persa per passo
    decomp_fraction: float = 0.9     # quota di (energia+corpo) che diventa organico alla morte

    # --- metabolismo ---
    base_cost: float = 0.20
    pred_upkeep: float = 0.30        # costo fisso dell'essere predatore (x pred)
    move_upkeep: float = 0.10        # costo fisso della motilità (x gene move)
    move_cost: float = 0.20          # costo di ogni spostamento
    spec_exp: float = 2.0            # esponente di specializzazione (>1 premia gli specialisti)

    # --- nutrizione ---
    photo_gain: float = 3.0
    sapro_rate: float = 1.0          # organico massimo assorbito per passo
    sapro_eff: float = 0.8
    pred_eff: float = 0.5

    # --- riproduzione ---
    body_cost: float = 5.0           # energia per costruire un corpo (restituita alla morte)
    div_min: float = 10.0
    div_max: float = 60.0
    max_age: int = 600
    max_bonds: int = 8

    # --- mutazione ---
    mut_min: float = 0.005
    mut_max: float = 0.15

    # --- immigrazione (cellule casuali che compaiono: mantiene la diversità) ---
    immigration_rate: float = 0.5    # cellule nuove per passo (es. 0.5 = una ogni 2 passi)

    # --- sicurezza ---
    reseed_on_extinction: bool = True

    def to_dict(self):
        return asdict(self)
