"""Simulation engine: grid world, cells, local rules.

Headless: no graphics dependencies. The grid is toroidal in x, and y = depth
(row 0 = lit surface, last row = seabed).
"""
import random

import numpy as np

from .config import Config

# Gene indices
G_PHOTO, G_SAPRO, G_PRED, G_MOVE, G_DIV, G_CHILD, G_ATTACH, G_SHARE, G_MUT = range(9)
N_GENES = 9
GENE_NAMES = ["photo", "sapro", "pred", "move", "div", "child", "attach", "share", "mut"]

NEIGH8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
STRATEGIES = ["photo", "sapro", "pred"]


class Cell:
    __slots__ = (
        "id", "x", "y", "energy", "age", "genes", "bonds", "alive", "lineage",
        "photo", "sapro", "pred", "photo_k", "sapro_k", "pred_k",
        "move", "div_thr", "child_frac", "attach", "share", "mut_sigma", "upkeep",
    )

    def __init__(self, cid, x, y, energy, genes, lineage, cfg):
        self.id = cid
        self.x = x
        self.y = y
        self.energy = energy
        self.age = 0
        self.genes = genes
        self.bonds = set()
        self.alive = True
        self.lineage = lineage
        self.express(cfg)

    def __hash__(self):
        # Hash by the world-unique, seed-deterministic id rather than the default
        # id()-based hash: iteration order of `bonds` sets (energy sharing) must not
        # depend on memory addresses, or the same seed yields different histories.
        # Equality stays identity, which is consistent because ids are unique.
        return self.id

    def express(self, cfg):
        """Genotype -> phenotype (derived traits, computed once)."""
        g = self.genes
        s = g[G_PHOTO] + g[G_SAPRO] + g[G_PRED] or 1e-9
        self.photo = g[G_PHOTO] / s
        self.sapro = g[G_SAPRO] / s
        self.pred = g[G_PRED] / s
        e = cfg.spec_exp
        self.photo_k = self.photo ** e
        self.sapro_k = self.sapro ** e
        self.pred_k = self.pred ** e
        self.move = g[G_MOVE]
        self.div_thr = cfg.div_min + g[G_DIV] * (cfg.div_max - cfg.div_min)
        self.child_frac = 0.2 + 0.6 * g[G_CHILD]
        self.attach = g[G_ATTACH]
        self.share = 0.5 * g[G_SHARE]
        self.mut_sigma = cfg.mut_min + g[G_MUT] * (cfg.mut_max - cfg.mut_min)
        self.upkeep = cfg.base_cost + cfg.pred_upkeep * self.pred + cfg.move_upkeep * self.move

    @property
    def strategy(self):
        t = (self.photo, self.sapro, self.pred)
        return STRATEGIES[t.index(max(t))]


class World:
    def __init__(self, cfg: Config | None = None, seed: int | None = None):
        self.cfg = cfg or Config()
        self.seed = seed
        self.rng = random.Random(seed)
        W, H = self.cfg.width, self.cfg.height
        self.W, self.H = W, H
        self.grid = [None] * (W * H)
        self.cells: list[Cell] = []
        self.organic = np.full((H, W), self.cfg.organic_init, dtype=np.float64)
        rows = np.arange(H, dtype=np.float64)
        self.base_light = self.cfg.light_max * np.exp(-rows / self.cfg.light_depth)
        self.light = np.tile(self.base_light[:, None], (1, W))
        self.step_count = 0
        self.next_id = 0
        self.births = 0
        self.deaths = 0
        self.kills = 0
        self.extinctions = 0
        self.seed_population(self.cfg.initial_cells)

    # ------------------------------------------------------------------ setup
    def random_genes(self):
        return [self.rng.random() for _ in range(N_GENES)]

    def seed_population(self, n):
        free = [i for i, c in enumerate(self.grid) if c is None]
        self.rng.shuffle(free)
        for i in free[:n]:
            x, y = i % self.W, i // self.W
            cid = self._new_id()
            self._place(Cell(cid, x, y, self.cfg.initial_energy, self.random_genes(), cid, self.cfg))

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
            b.bonds.discard(c)
        c.bonds.clear()
        if organic_amount > 0:
            self.organic[c.y, c.x] += organic_amount
        self.deaths += 1

    # ------------------------------------------------------------ fields
    def update_light(self):
        """Light = depth attenuation x shading by the cells above."""
        H, W = self.H, self.W
        occ = np.zeros((H, W), dtype=np.float64)
        if self.cells:
            xs = np.fromiter((c.x for c in self.cells), dtype=np.int32, count=len(self.cells))
            ys = np.fromiter((c.y for c in self.cells), dtype=np.int32, count=len(self.cells))
            occ[ys, xs] = 1.0
        above = np.cumsum(occ, axis=0) - occ
        self.light = self.base_light[:, None] * np.power(self.cfg.shade, above)

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
        o[:-1] -= moved
        o[1:] += moved
        # decay
        o *= 1.0 - cfg.organic_decay

    # ------------------------------------------------------------- step
    def step(self):
        cfg, rng = self.cfg, self.rng
        grid, W = self.grid, self.W
        org, light = self.organic, self.light
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
                    if rand() < c.attach and len(c.bonds) < cfg.max_bonds:
                        c.bonds.add(child)
                        child.bonds.add(c)

        self.cells = [c for c in cells if c.alive] + newborns
        self.update_organic()
        self.step_count += 1

        if cfg.immigration_rate > 0.0:
            k = int(cfg.immigration_rate)
            if rng.random() < cfg.immigration_rate - k:
                k += 1
            for _ in range(k):
                i = rng.randrange(self.W * self.H)
                if self.grid[i] is None:
                    cid = self._new_id()
                    self._place(Cell(cid, i % self.W, i // self.W, cfg.initial_energy,
                                     self.random_genes(), cid, cfg))

        if not self.cells and cfg.reseed_on_extinction:
            self.extinctions += 1
            self.seed_population(cfg.initial_cells)

    # ------------------------------------------------------------- stats
    def stats(self):
        cells = self.cells
        n = len(cells)
        s = {
            "step": self.step_count,
            "population": n,
            "photo": 0, "sapro": 0, "pred": 0,
            "in_colony": 0,
            "lineages": len({c.lineage for c in cells}),
            "energy_cells": round(sum(c.energy for c in cells), 2),
            "organic_total": round(float(self.organic.sum()), 2),
            "births": self.births, "deaths": self.deaths, "kills": self.kills,
            "extinctions": self.extinctions,
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
        return s

    def cell_at(self, x, y):
        if 0 <= x < self.W and 0 <= y < self.H:
            return self.grid[y * self.W + x]
        return None
