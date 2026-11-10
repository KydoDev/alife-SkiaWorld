"""Simulation engine: grid world, cells, local rules.

Headless: no graphics dependencies. The grid is toroidal in x, and y = depth
(row 0 = lit surface, last row = seabed).
"""
import math
import random

import numpy as np

from .config import Config
from .species import ORIGIN_IMMIGRANT, ORIGIN_SEED, SpeciesTracker
from .terrain import Terrain, generate_terrain

# Gene indices. New genes are appended so existing indices keep their meaning.
G_PHOTO, G_SAPRO, G_PRED, G_MOVE, G_DIV, G_CHILD, G_ATTACH, G_SHARE, G_MUT, G_CHEMO = range(10)
N_GENES = 10
GENE_NAMES = ["photo", "sapro", "pred", "move", "div", "child", "attach", "share", "mut", "chemo"]

NEIGH8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
STRATEGIES = ["photo", "sapro", "pred", "chemo"]


class Cell:
    __slots__ = (
        "id", "x", "y", "energy", "age", "genes", "bonds", "alive", "lineage",
        "photo", "sapro", "pred", "chemo", "photo_k", "sapro_k", "pred_k", "chemo_k",
        "move", "div_thr", "child_frac", "attach", "share", "mut_sigma", "upkeep",
        "species",
    )

    def __init__(self, cid, x, y, energy, genes, lineage, cfg):
        self.id = cid
        self.x = x
        self.y = y
        self.energy = energy
        self.age = 0
        self.genes = genes
        # Insertion-ordered dict used as an ordered set (values unused). Energy sharing
        # iterates it, so its order is part of the simulation state: a dict keeps the
        # same order across runs AND across save/load, which a set cannot guarantee.
        self.bonds: dict[Cell, None] = {}
        self.alive = True
        self.lineage = lineage
        self.species = 0          # set by SpeciesTracker; never read by the dynamics
        self.express(cfg)

    def __hash__(self):
        # Hash by the world-unique, seed-deterministic id rather than the default
        # id()-based hash, so nothing keyed by cells depends on memory addresses.
        # Equality stays identity, which is consistent because ids are unique.
        return self.id

    def express(self, cfg):
        """Genotype -> phenotype (derived traits, computed once)."""
        g = self.genes
        s = g[G_PHOTO] + g[G_SAPRO] + g[G_PRED] + g[G_CHEMO] or 1e-9
        self.photo = g[G_PHOTO] / s
        self.sapro = g[G_SAPRO] / s
        self.pred = g[G_PRED] / s
        self.chemo = g[G_CHEMO] / s
        e = cfg.spec_exp
        self.photo_k = self.photo ** e
        self.sapro_k = self.sapro ** e
        self.pred_k = self.pred ** e
        self.chemo_k = self.chemo ** e
        self.move = g[G_MOVE]
        self.div_thr = cfg.div_min + g[G_DIV] * (cfg.div_max - cfg.div_min)
        self.child_frac = 0.2 + 0.6 * g[G_CHILD]
        self.attach = g[G_ATTACH]
        self.share = 0.5 * g[G_SHARE]
        self.mut_sigma = cfg.mut_min + g[G_MUT] * (cfg.mut_max - cfg.mut_min)
        self.upkeep = cfg.base_cost + cfg.pred_upkeep * self.pred + cfg.move_upkeep * self.move

    @property
    def strategy(self):
        t = (self.photo, self.sapro, self.pred, self.chemo)
        return STRATEGIES[t.index(max(t))]


class World:
    def __init__(self, cfg: Config | None = None, seed: int | None = None,
                 track_species: bool = True, populate: bool = True, terrain: Terrain | None = None):
        """`populate=False` builds an empty world (used by `persistence.load_world`).
        `terrain=None` generates it from `Config` (flat by default)."""
        self.cfg = (cfg or Config()).validate()
        self.seed = seed
        self.rng = random.Random(seed)
        W, H = self.cfg.width, self.cfg.height
        self.W, self.H = W, H
        self.grid = [None] * (W * H)
        self.cells: list[Cell] = []
        self.set_terrain(terrain if terrain is not None else generate_terrain(self.cfg, seed))
        self.organic = self.terrain.organic.copy()
        self.light = self.base_light.copy()
        self.step_count = 0
        self.next_id = 0
        self.births = 0
        self.deaths = 0
        self.kills = 0
        self.extinctions = 0
        self.now = 0              # step being executed (step_count + 1 during step())
        self.tracker = (SpeciesTracker(self.cfg.species_threshold, self.cfg.novelty_activity,
                                       self.cfg.species_prune_peak) if track_species else None)
        if populate:
            self.seed_population(self.cfg.initial_cells)

    # ------------------------------------------------------------------ setup
    def set_terrain(self, terrain: Terrain):
        """Install the static maps and everything derived from them."""
        H, W = self.H, self.W
        shapes = (terrain.rock.shape, terrain.chem.shape, terrain.organic.shape, terrain.sun.shape)
        if shapes != ((H, W), (H, W), (H, W), (W,)):
            raise ValueError(f"terrain maps do not match the {W}x{H} world")
        self.terrain = terrain
        rock = terrain.rock
        rows = np.arange(H, dtype=np.float64)
        depth = self.cfg.light_max * np.exp(-rows / self.cfg.light_depth)
        # rocks are opaque: no light at or below the first rock in a column
        lit = np.cumsum(rock, axis=0) == 0
        self.base_light = depth[:, None] * terrain.sun[None, :] * lit
        self.blocked = rock.ravel().tolist()            # flat list: fast per-tile lookup in the hot loop
        self.has_rock = bool(rock.any())
        self.chem = terrain.chem
        self.has_chem = bool(terrain.chem.any())
        # organic matter does not sink into rock (it settles on the seabed instead)
        self.sink_mask = (~rock[1:]).astype(np.float64) if self.has_rock else None

    def random_genes(self):
        return [self.rng.random() for _ in range(N_GENES)]

    def seed_population(self, n):
        blocked = self.blocked
        free = [i for i, c in enumerate(self.grid) if c is None and not blocked[i]]
        self.rng.shuffle(free)
        for i in free[:n]:
            x, y = i % self.W, i // self.W
            cid = self._new_id()
            cell = Cell(cid, x, y, self.cfg.initial_energy, self.random_genes(), cid, self.cfg)
            self._place(cell)
            if self.tracker is not None:
                self.tracker.on_root(cell, ORIGIN_SEED, self.now)

    # --------------------------------------------------------------- helpers
    def _new_id(self):
        self.next_id += 1
        return self.next_id

    def _place(self, cell):
        self.grid[cell.y * self.W + cell.x] = cell
        self.cells.append(cell)

    def neighbors(self, x, y):
        W, H = self.W, self.H
        out = []
        for dx, dy in NEIGH8:
            ny = y + dy
            if 0 <= ny < H:
                out.append(((x + dx) % W, ny))
        return out

    def random_empty_neighbor(self, x, y):
        grid, W = self.grid, self.W
        if self.has_rock:
            blocked = self.blocked
            free = [(nx, ny) for nx, ny in self.neighbors(x, y)
                    if grid[ny * W + nx] is None and not blocked[ny * W + nx]]
        else:
            free = [(nx, ny) for nx, ny in self.neighbors(x, y) if grid[ny * W + nx] is None]
        return self.rng.choice(free) if free else None

    def random_prey(self, c):
        grid, W = self.grid, self.W
        prey = []
        for nx, ny in self.neighbors(c.x, c.y):
            o = grid[ny * W + nx]
            if o is not None and o not in c.bonds:
                prey.append(o)
        return self.rng.choice(prey) if prey else None

    def mutate(self, genes, sigma):
        g = self.rng.gauss
        return [min(1.0, max(0.0, v + g(0.0, sigma))) for v in genes]

    def kill(self, c, organic_amount):
        c.alive = False
        self.grid[c.y * self.W + c.x] = None
        for b in c.bonds:
            b.bonds.pop(c, None)
        c.bonds.clear()
        if organic_amount > 0:
            self.organic[c.y, c.x] += organic_amount
        self.deaths += 1
        if self.tracker is not None:
            self.tracker.on_death(c, self.now)

    # ------------------------------------------------------------ fields
    def light_factor(self, t=None):
        """Global light multiplier at step `t` (default: the current step): day/night x season.

        A pure function of the step index, so cycles add no save state."""
        cfg = self.cfg
        if cfg.day_amplitude == 0.0 and cfg.season_amplitude == 0.0:
            return 1.0
        t = self.now if t is None else t
        f = 1.0
        if cfg.day_amplitude:
            f *= 1.0 + cfg.day_amplitude * math.sin(2.0 * math.pi * t / cfg.day_length)
        if cfg.season_amplitude:
            f *= 1.0 + cfg.season_amplitude * math.sin(2.0 * math.pi * t / cfg.year_length)
        return f

    def update_light(self):
        """Light = depth attenuation x shading by the cells above x day/season factor."""
        H, W = self.H, self.W
        occ = np.zeros((H, W), dtype=np.float64)
        if self.cells:
            xs = np.fromiter((c.x for c in self.cells), dtype=np.int32, count=len(self.cells))
            ys = np.fromiter((c.y for c in self.cells), dtype=np.int32, count=len(self.cells))
            occ[ys, xs] = 1.0
        above = np.cumsum(occ, axis=0) - occ
        self.light = self.base_light * np.power(self.cfg.shade, above)
        f = self.light_factor()
        if f != 1.0:
            self.light *= f

    def update_organic(self):
        cfg, o = self.cfg, self.organic
        # diffusion (toroidal x, closed edges in y)
        up = np.vstack([o[:1], o[:-1]])
        down = np.vstack([o[1:], o[-1:]])
        left = np.roll(o, 1, axis=1)
        right = np.roll(o, -1, axis=1)
        o += cfg.organic_diffusion * ((up + down + left + right) * 0.25 - o)
        # sinking toward the seabed
        moved = o[:-1] * cfg.organic_sink
        if self.sink_mask is not None:
            moved *= self.sink_mask
        o[:-1] -= moved
        o[1:] += moved
        # decay
        o *= 1.0 - cfg.organic_decay

    # ------------------------------------------------------------- step
    def step(self):
        cfg, rng = self.cfg, self.rng
        grid, W = self.grid, self.W
        org, light = self.organic, self.light
        tracker = self.tracker
        chem = self.chem if self.has_chem else None
        self.now = self.step_count + 1
        self.update_light()
        light = self.light

        cells = self.cells
        rng.shuffle(cells)
        newborns = []
        rand = rng.random

        for c in cells:
            if not c.alive:
                continue
            c.age += 1
            x, y = c.x, c.y

            # 1-3: metabolism and feeding
            e = c.energy - c.upkeep
            if c.photo_k > 0.0:
                e += cfg.photo_gain * c.photo_k * light[y, x]
            if c.sapro_k > 0.0:
                avail = org[y, x]
                if avail > 0.0:
                    take = min(avail, cfg.sapro_rate * c.sapro_k)
                    org[y, x] = avail - take
                    e += cfg.sapro_eff * take
            if chem is not None and c.chemo_k > 0.0:
                e += cfg.chemo_gain * c.chemo_k * chem[y, x]
            c.energy = e

            # 4: predation
            if c.pred_k > 0.0 and rand() < c.pred_k:
                prey = self.random_prey(c)
                if prey is not None:
                    food = max(prey.energy, 0.0) + cfg.body_cost
                    c.energy += cfg.pred_eff * food
                    self.kill(prey, (1.0 - cfg.pred_eff) * food)
                    self.kills += 1

            # 5: movement (unbonded cells only)
            if not c.bonds and c.move > 0.0 and rand() < c.move:
                dest = self.random_empty_neighbor(x, y)
                if dest is not None:
                    grid[y * W + x] = None
                    c.x, c.y = dest
                    grid[c.y * W + c.x] = c
                    c.energy -= cfg.move_cost

            # 6: energy sharing within the colony
            if c.bonds and c.share > 0.0:
                for b in c.bonds:
                    diff = c.energy - b.energy
                    if diff > 0.0:
                        t = diff * c.share * 0.5
                        c.energy -= t
                        b.energy += t

            # 8a: death
            if c.energy <= 0.0 or c.age > cfg.max_age:
                self.kill(c, cfg.decomp_fraction * (max(c.energy, 0.0) + cfg.body_cost))
                continue

            # 7: division
            if c.energy >= c.div_thr:
                spot = self.random_empty_neighbor(c.x, c.y)
                if spot is not None:
                    c.energy -= cfg.body_cost
                    child_e = c.energy * c.child_frac
                    c.energy -= child_e
                    child = Cell(self._new_id(), spot[0], spot[1], child_e,
                                 self.mutate(c.genes, c.mut_sigma), c.lineage, cfg)
                    grid[child.y * W + child.x] = child
                    newborns.append(child)
                    self.births += 1
                    if tracker is not None:
                        tracker.on_birth(child, c, self.now)
                    if rand() < c.attach and len(c.bonds) < cfg.max_bonds:
                        c.bonds[child] = None
                        child.bonds[c] = None

        # Newborns can be eaten in their birth step: filter them too, or dead ghosts
        # stay in `cells` for a step (double-counted energy, phantom shading).
        self.cells = [c for c in cells if c.alive] + [c for c in newborns if c.alive]
        self.update_organic()
        self.step_count += 1

        if cfg.immigration_rate > 0.0:
            k = int(cfg.immigration_rate)
            if rng.random() < cfg.immigration_rate - k:
                k += 1
            for _ in range(k):
                i = rng.randrange(self.W * self.H)
                if self.grid[i] is None and not self.blocked[i]:
                    cid = self._new_id()
                    cell = Cell(cid, i % self.W, i // self.W, cfg.initial_energy,
                                self.random_genes(), cid, cfg)
                    self._place(cell)
                    if tracker is not None:
                        tracker.on_root(cell, ORIGIN_IMMIGRANT, self.now)

        if not self.cells and cfg.reseed_on_extinction:
            self.extinctions += 1
            self.seed_population(cfg.initial_cells)

        if tracker is not None:
            tracker.end_step(self.step_count)

    # ------------------------------------------------------------- stats
    def stats(self):
        cells = self.cells
        n = len(cells)
        s = {
            "step": self.step_count,
            "population": n,
            "photo": 0, "sapro": 0, "pred": 0, "chemo": 0,
            "in_colony": 0,
            "lineages": len({c.lineage for c in cells}),
            "energy_cells": round(sum(c.energy for c in cells), 2),
            "organic_total": round(float(self.organic.sum()), 2),
            "births": self.births, "deaths": self.deaths, "kills": self.kills,
            "extinctions": self.extinctions,
            "light_factor": round(self.light_factor(self.step_count), 4),
        }
        if n:
            for c in cells:
                s[c.strategy] += 1
                if c.bonds:
                    s["in_colony"] += 1
            for gi, name in enumerate(GENE_NAMES):
                s["mean_" + name] = round(sum(c.genes[gi] for c in cells) / n, 4)
            s["mean_age"] = round(sum(c.age for c in cells) / n, 1)
        else:
            for name in GENE_NAMES:
                s["mean_" + name] = 0.0
            s["mean_age"] = 0.0
        if self.tracker is not None:
            s.update(self.tracker.stats())
        return s

    def cell_at(self, x, y):
        if 0 <= x < self.W and 0 <= y < self.H:
            return self.grid[y * self.W + x]
        return None
