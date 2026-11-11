"""Simulation engine: grid world, cells, local rules.

Headless: no graphics dependencies. The grid is toroidal in x, and y = depth
(row 0 = lit surface, last row = seabed).
"""
import math
import random

import numpy as np

from .config import Config
from .species import ORIGIN_IMMIGRANT, ORIGIN_SEED, SpeciesTracker, genome_distance
from .terrain import Terrain, generate_terrain

# Gene indices. New genes are appended so existing indices keep their meaning.
G_PHOTO, G_SAPRO, G_PRED, G_MOVE, G_DIV, G_CHILD, G_ATTACH, G_SHARE, G_MUT, G_CHEMO = range(10)
# F3 sensor weights (gene g -> weight 2g - 1): how much a tile's light, organic matter, chemical
# energy, kin, strangers and danger attract (> 0) or repel (< 0) a moving cell.
G_W_LIGHT, G_W_ORGANIC, G_W_CHEM, G_W_KIN, G_W_STRANGER, G_W_DANGER = range(10, 16)
N_GENES = 16
GENE_NAMES = ["photo", "sapro", "pred", "move", "div", "child", "attach", "share", "mut", "chemo",
              "w_light", "w_organic", "w_chem", "w_kin", "w_stranger", "w_danger"]

NEIGH8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
# Candidate tiles of a sensed move: stay put, or one of the 8 neighbours.
# VIEWS[(top, bottom)][d] = how many of the mover's neighbour tiles inside the grid touch candidate d;
# it normalises the social inputs (on the surface or floor row some neighbour tiles do not exist).


def _view(top, bottom):
    tiles = [n for n in NEIGH8 if not (top and n[1] == -1) and not (bottom and n[1] == 1)]
    return {d: max(1, sum(1 for n in tiles if n != d and abs(n[0] - d[0]) <= 1 and abs(n[1] - d[1]) <= 1))
            for d in [(0, 0), *NEIGH8]}


VIEWS = {(top, bottom): _view(top, bottom) for top in (False, True) for bottom in (False, True)}
STRATEGIES = ["photo", "sapro", "pred", "chemo"]

# F4 rule genes: 4 values in [0, 1] = (condition, threshold, target, intensity). While the condition on the
# cell's own state holds, the rule adds its intensity (2v - 1) to a sensor weight or shifts the division threshold.
RULE_CONDITIONS = ("always", "energy>", "energy<", "light>", "light<")
RULE_TARGETS = (*GENE_NAMES[G_W_LIGHT:G_W_DANGER + 1], "div")
RULE_DIV = len(RULE_TARGETS) - 1
RULE_LEN = 4


def decode_rule(r):
    """Rule gene -> (condition index, threshold, target index, intensity in [-1, 1])."""
    return (min(len(RULE_CONDITIONS) - 1, int(r[0] * len(RULE_CONDITIONS))), r[1],
            min(len(RULE_TARGETS) - 1, int(r[2] * len(RULE_TARGETS))), 2.0 * r[3] - 1.0)


def genetic_diet(photo, sapro, chemo):
    """F5b: the genetic split of the non-predatory share among photo / sapro / chemo (sums to 1)."""
    s = photo + sapro + chemo
    return (photo / s, sapro / s, chemo / s) if s > 0.0 else (1 / 3, 1 / 3, 1 / 3)


def describe_rule(r):
    cond, thr, target, w = decode_rule(r)
    when = "always" if cond == 0 else f"{RULE_CONDITIONS[cond]}{thr:.2f}"
    return f"{when} {RULE_TARGETS[target]} {w:+.2f}"


class Cell:
    __slots__ = (
        "id", "x", "y", "energy", "age", "genes", "bonds", "alive", "lineage",
        "photo", "sapro", "pred", "chemo", "photo_k", "sapro_k", "pred_k", "chemo_k",
        "move", "div_thr", "child_frac", "attach", "share", "mut_sigma", "upkeep",
        "sense", "species", "rules", "rule_fx", "sex_p", "plast_p", "diet", "hgt_p", "armor_p",
    )

    def __init__(self, cid, x, y, energy, genes, lineage, cfg, rules=(), sex_p=0.0, plast_p=0.0, hgt_p=0.0,
                 armor_p=0.0):
        self.id = cid
        self.x = x
        self.y = y
        self.energy = energy
        self.age = 0
        self.genes = genes
        self.rules = rules        # F4 rule genes (list of 4-value lists); empty unless open_genome is on
        self.sex_p = sex_p        # F5a propensity to mate at division; 0 unless sex is on
        self.plast_p = plast_p    # F5b rate of diet acclimation; 0 unless plasticity is on
        self.diet = ()            # F5b acclimated (photo, sapro, chemo) split; empty unless plasticity is on
        self.hgt_p = hgt_p        # F5c propensity to copy a neighbour's gene; 0 unless hgt is on
        self.armor_p = armor_p    # F5e armour: share of attacks it can repel; 0 unless defence is on
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
        self.sense = tuple(2.0 * v - 1.0 for v in g[G_W_LIGHT:G_W_DANGER + 1])
        if cfg.sensing:
            self.upkeep += cfg.sense_upkeep * sum(abs(w) for w in self.sense) / len(self.sense)
        self.rule_fx = ()
        if cfg.open_genome:
            self.upkeep += cfg.rule_upkeep * len(self.rules)
            if not cfg.rules_neutral:
                self.rule_fx = tuple(decode_rule(r) for r in self.rules)
        if cfg.plasticity:
            self.upkeep += cfg.plastic_upkeep * self.plast_p
            self.diet = genetic_diet(self.photo, self.sapro, self.chemo)
            self.apply_diet(cfg)
        if cfg.hgt:
            self.upkeep += cfg.hgt_upkeep * self.hgt_p
        if cfg.defence:
            self.upkeep += cfg.defence_upkeep * self.armor_p

    def apply_diet(self, cfg):
        """F5b: phenotype shares from the acclimated diet; the predation share stays genetic.
        Always used when plasticity is on (also at birth), so a resumed world derives the same floats."""
        g = self.genes
        # all four feeding genes at 0: the cell cannot feed, as with plasticity off (not a 1/3 generalist)
        non_pred = 1.0 - self.pred if (g[G_PHOTO] or g[G_SAPRO] or g[G_PRED] or g[G_CHEMO]) else 0.0
        p, s, ch = self.diet
        e = cfg.spec_exp
        self.photo, self.sapro, self.chemo = non_pred * p, non_pred * s, non_pred * ch
        self.photo_k = self.photo ** e
        self.sapro_k = self.sapro ** e
        self.chemo_k = self.chemo ** e

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
        self.sex_births = 0       # F5a: divisions that recombined with a partner
        self.hgt_events = 0       # F5c: genes copied from a neighbour
        self.hgt_foreign = 0      # F5c: ... of which from a donor of another lineage
        self.defended = 0         # F5e: attacks repelled by armour
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
        # Transcendentals go through libm (`math`), never numpy's SIMD loops: on AVX-512 CPUs those are not
        # correctly rounded, so they differ from libm and from the Rust kernel (docs/G2_PLAN.md, M2 on Linux).
        cfg = self.cfg
        depth = cfg.light_max * np.array([math.exp(-float(y) / cfg.light_depth) for y in range(H)])
        self.shade_pow = np.array([math.pow(cfg.shade, float(k)) for k in range(H + 1)])   # shade ** cells above
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
            cell = Cell(cid, x, y, self.cfg.initial_energy, self.random_genes(), cid, self.cfg,
                        sex_p=self.rng.random() if self.cfg.sex else 0.0,
                        plast_p=self.rng.random() if self.cfg.plasticity else 0.0,
                        hgt_p=self.rng.random() if self.cfg.hgt else 0.0,
                        armor_p=self.rng.random() if self.cfg.defence else 0.0)
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

    def rule_effects(self, c, light_here):
        """F4: apply the rules whose condition holds for this cell now. Returns the effective sensor weights
        and the shift of the division threshold (energy units). Conditions read only the cell's own state
        (energy / div_max, light here / light_max), so this runs once per cell per step."""
        cfg = self.cfg
        e = c.energy / cfg.div_max
        lt = light_here / cfg.light_max if cfg.light_max > 0 else 0.0
        sense, div = list(c.sense), 0.0
        for cond, thr, target, w in c.rule_fx:
            if (cond == 0 or (cond == 1 and e > thr) or (cond == 2 and e < thr)
                    or (cond == 3 and lt > thr) or (cond == 4 and lt < thr)):
                if target == RULE_DIV:
                    div += w
                else:
                    sense[target] += w
        return sense, div * cfg.rule_div_shift * (cfg.div_max - cfg.div_min)

    def mutate_rules(self, rules, sigma):
        """F4 variation of the rule genes: point mutation of every value, then possibly one duplication
        (the copy next to the original), one deletion and one new random rule, within max_rules."""
        cfg, rng = self.cfg, self.rng
        g = rng.gauss
        out = [[min(1.0, max(0.0, v + g(0.0, sigma))) for v in r] for r in rules]
        if rng.random() < cfg.rule_dup_rate and out and len(out) < cfg.max_rules:
            i = rng.randrange(len(out))
            out.insert(i + 1, list(out[i]))
        if rng.random() < cfg.rule_del_rate and out:
            del out[rng.randrange(len(out))]
        if rng.random() < cfg.rule_new_rate and len(out) < cfg.max_rules:
            out.append([rng.random() for _ in range(RULE_LEN)])
        return out

    def find_mate(self, c):
        """F5a: a random cell within mate_radius whose fixed genes are within mate_distance, or None."""
        cfg, grid, W, H = self.cfg, self.grid, self.W, self.H
        r, limit = cfg.mate_radius, cfg.mate_distance
        found, seen = [], set()           # seen: on a narrow world the x-wrap revisits tiles
        for dy in range(-r, r + 1):
            y = c.y + dy
            if not 0 <= y < H:
                continue
            for dx in range(-r, r + 1):
                i = y * W + (c.x + dx) % W
                if i in seen:
                    continue
                seen.add(i)
                o = grid[i]
                if o is not None and o is not c and genome_distance(c.genes, o.genes) < limit:
                    found.append(o)
        return self.rng.choice(found) if found else None

    def offspring_genes(self, c, mate):
        """F5a: uniform crossover of the fixed genes (each from either parent), or the parent's own genes."""
        if mate is None:
            return c.genes
        rand = self.rng.random
        return [a if rand() < 0.5 else b for a, b in zip(c.genes, mate.genes)]

    def offspring_sex_p(self, c):
        """F5a: the dividing parent's propensity, mutated. Never the mate's: mates are not chosen by their
        propensity, so taking it half the time would pull the mean towards the population mean by itself
        (by about share_of_matings / 2 x variance per generation) and fake selection against sex."""
        return min(1.0, max(0.0, c.sex_p + self.rng.gauss(0.0, c.mut_sigma)))

    def offspring_plast_p(self, c):
        """F5b: the dividing parent's acclimation rate, mutated (never a mate's, as for sex_p)."""
        return min(1.0, max(0.0, c.plast_p + self.rng.gauss(0.0, c.mut_sigma)))

    def offspring_hgt_p(self, c):
        """F5c: the dividing parent's transfer propensity, mutated (never a mate's, as for sex_p)."""
        return min(1.0, max(0.0, c.hgt_p + self.rng.gauss(0.0, c.mut_sigma)))

    def offspring_armor_p(self, c):
        """F5e: the dividing parent's armour, mutated (never a mate's, as for sex_p)."""
        return min(1.0, max(0.0, c.armor_p + self.rng.gauss(0.0, c.mut_sigma)))

    def transfer_gene(self, c):
        """F5c: copy one random fixed gene from a random neighbour (any lineage, bonded or not) and re-express.

        The genome changes for life and is inherited; with plasticity on, re-expression resets the diet to the
        new genetic split. Species labels stay as assigned at birth (the tracker is not told)."""
        grid, W = self.grid, self.W
        donors = [o for nx, ny in self.neighbors(c.x, c.y) if (o := grid[ny * W + nx]) is not None]
        if not donors:
            return
        donor = self.rng.choice(donors)
        k = self.rng.randrange(N_GENES)
        genes = list(c.genes)
        genes[k] = donor.genes[k]
        c.genes = genes
        c.express(self.cfg)
        self.hgt_events += 1
        if donor.lineage != c.lineage:
            self.hgt_foreign += 1

    def acclimate(self, c, light_here, organic_here, chem_here):
        """F5b: move the diet towards the split of what each diet would yield here at full specialisation.
        Deterministic (no RNG); with nothing to gain here the diet stays put."""
        cfg = self.cfg
        yp = cfg.photo_gain * light_here
        ys = cfg.sapro_eff * min(organic_here, cfg.sapro_rate)
        yc = cfg.chemo_gain * chem_here
        total = yp + ys + yc
        if total <= 0.0:
            return
        r = c.plast_p * cfg.plastic_rate
        p, s, ch = c.diet
        c.diet = (p + r * (yp / total - p), s + r * (ys / total - s), ch + r * (yc / total - ch))
        c.apply_diet(cfg)

    def sensed_move(self, c, sense=None):
        """F3 directed movement: score staying put and each free neighbour tile, return the best
        destination, or None to stay.

        Perception has radius 1: the environment of each candidate tile (light, organic matter,
        chemical energy) and the cells among the mover's neighbours that touch it (kin = same
        lineage, strangers, danger = predator share of all of them, kin included, since kin predators
        eat kin too), as densities in [0, 1] over the neighbour tiles inside the grid.
        Score = sum(weight x input) + noise; the noise breaks ties, so zero weights = random walk."""
        cfg, grid, W, H = self.cfg, self.grid, self.W, self.H
        x, y = c.x, c.y
        blocked = self.blocked if self.has_rock else None
        social = []                                   # (dx, dy, is_kin, predator share)
        cands = [(0, 0, x, y)]
        for dx, dy in NEIGH8:
            ny = y + dy
            if not 0 <= ny < H:
                continue
            nx = (x + dx) % W
            o = grid[ny * W + nx]
            if o is None:
                if blocked is None or not blocked[ny * W + nx]:
                    cands.append((dx, dy, nx, ny))
            else:
                social.append((dx, dy, o.lineage == c.lineage, o.pred))
        if len(cands) == 1:
            return None
        wl, wo, wc, wk, ws, wd = c.sense if sense is None else sense
        light, org = self.light, self.organic
        chem = self.chem if self.has_chem else None
        inv_l = 1.0 / cfg.light_max if cfg.light_max > 0 else 0.0
        noise, rand = cfg.sense_noise, self.rng.random
        view = VIEWS[(y == 0, y == H - 1)]
        best, best_score = cands[0], -math.inf
        for dx, dy, tx, ty in cands:
            o = org[ty, tx]
            s = wl * light[ty, tx] * inv_l + wo * o / (o + 1.0)
            if chem is not None:
                ch = chem[ty, tx]
                s += wc * ch / (ch + 1.0)
            if social:
                kin = strangers = danger = 0.0
                for sx, sy, is_kin, pred in social:
                    if -1 <= sx - dx <= 1 and -1 <= sy - dy <= 1 and (sx != dx or sy != dy):
                        if is_kin:
                            kin += 1.0
                        else:
                            strangers += 1.0
                        danger += pred
                s += (wk * kin + ws * strangers + wd * danger) / view[(dx, dy)]
            s += noise * rand()
            if s > best_score:
                best, best_score = (dx, dy, tx, ty), s
        return None if best[0] == 0 and best[1] == 0 else (best[2], best[3])

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
        occ = np.zeros((H, W), dtype=np.intp)
        if self.cells:
            xs = np.fromiter((c.x for c in self.cells), dtype=np.int32, count=len(self.cells))
            ys = np.fromiter((c.y for c in self.cells), dtype=np.int32, count=len(self.cells))
            occ[ys, xs] = 1
        above = np.cumsum(occ, axis=0) - occ          # cells above each tile, 0..H-1
        self.light = self.base_light * self.shade_pow[above]
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
        sensing = cfg.sensing
        open_genome = cfg.open_genome
        sex_on, mating = cfg.sex, cfg.sex and not cfg.sex_neutral
        plastic_on, plastic = cfg.plasticity, cfg.plasticity and not cfg.plastic_neutral
        hgt_on, transfer = cfg.hgt, cfg.hgt and not cfg.hgt_neutral
        hgt_rate = cfg.hgt_rate
        defence_on, armour = cfg.defence, cfg.defence and not cfg.defence_neutral
        defence_strength = cfg.defence_strength
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

            # 0: F5c horizontal transfer, before feeding so the whole turn uses one phenotype
            if transfer and rand() < c.hgt_p * hgt_rate:
                self.transfer_gene(c)
            # 1-3: metabolism and feeding (F5b: the diet first acclimates to this tile)
            if plastic and c.plast_p > 0.0:
                self.acclimate(c, light[y, x], org[y, x], chem[y, x] if chem is not None else 0.0)
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
            fx = c.rule_fx                       # F4: active rules, evaluated once per step
            if fx:
                sense, div_shift = self.rule_effects(c, light[y, x])

            # 4: predation
            if c.pred_k > 0.0 and rand() < c.pred_k:
                prey = self.random_prey(c)
                if prey is not None and armour and rand() < prey.armor_p * defence_strength:
                    prey = None                  # F5e: the armour repels the attack; nobody gains or loses
                    self.defended += 1
                if prey is not None:
                    food = max(prey.energy, 0.0) + cfg.body_cost
                    c.energy += cfg.pred_eff * food
                    self.kill(prey, (1.0 - cfg.pred_eff) * food)
                    self.kills += 1

            # 5: movement (unbonded cells only); F3 sensing steers it, otherwise a random walk
            if not c.bonds and c.move > 0.0 and rand() < c.move:
                if sensing:
                    dest = self.sensed_move(c, sense if fx else None)
                else:
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
            thr = c.div_thr
            if fx and div_shift:
                thr = min(cfg.div_max, max(cfg.div_min, thr + div_shift))
            if c.energy >= thr:
                spot = self.random_empty_neighbor(c.x, c.y)
                if spot is not None:
                    mate = None
                    # mating needs enough energy for its cost and the body, so no energy goes negative
                    if mating and rand() < c.sex_p and c.energy > cfg.sex_cost + cfg.body_cost:
                        mate = self.find_mate(c)
                        if mate is not None:
                            c.energy -= cfg.sex_cost
                            self.sex_births += 1
                    c.energy -= cfg.body_cost
                    child_e = c.energy * c.child_frac
                    c.energy -= child_e
                    genes = self.mutate(self.offspring_genes(c, mate) if mating else c.genes, c.mut_sigma)
                    rules = self.mutate_rules(c.rules, c.mut_sigma) if open_genome else ()
                    sex_p = self.offspring_sex_p(c) if sex_on else 0.0
                    plast_p = self.offspring_plast_p(c) if plastic_on else 0.0
                    hgt_p = self.offspring_hgt_p(c) if hgt_on else 0.0
                    armor_p = self.offspring_armor_p(c) if defence_on else 0.0
                    child = Cell(self._new_id(), spot[0], spot[1], child_e, genes, c.lineage, cfg, rules, sex_p,
                                 plast_p, hgt_p, armor_p)
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
                                self.random_genes(), cid, cfg, sex_p=rng.random() if cfg.sex else 0.0,
                                plast_p=rng.random() if cfg.plasticity else 0.0,
                                hgt_p=rng.random() if cfg.hgt else 0.0,
                                armor_p=rng.random() if cfg.defence else 0.0)
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
            "extinctions": self.extinctions, "sex_births": self.sex_births,
            "hgt_events": self.hgt_events, "hgt_foreign": self.hgt_foreign, "defended": self.defended,
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
            s["rules_mean"] = round(sum(len(c.rules) for c in cells) / n, 3)
            s["sex_p_mean"] = round(sum(c.sex_p for c in cells) / n, 4)
            s["plast_p_mean"] = round(sum(c.plast_p for c in cells) / n, 4)
            s["diet_shift"] = round(sum(self.diet_shift(c) for c in cells) / n, 4)
            s["hgt_p_mean"] = round(sum(c.hgt_p for c in cells) / n, 4)
            s["armor_p_mean"] = round(sum(c.armor_p for c in cells) / n, 4)
            s["rules_max"] = max(len(c.rules) for c in cells)
        else:
            for name in GENE_NAMES:
                s["mean_" + name] = 0.0
            s["mean_age"] = 0.0
            s["rules_mean"], s["rules_max"], s["sex_p_mean"] = 0.0, 0, 0.0
            s["plast_p_mean"], s["diet_shift"], s["hgt_p_mean"], s["armor_p_mean"] = 0.0, 0.0, 0.0, 0.0
        if self.tracker is not None:
            s.update(self.tracker.stats())
        return s

    @staticmethod
    def diet_shift(c):
        """F5b: how far the acclimated diet is from the genetic one (total variation distance, 0..1)."""
        if not c.diet:
            return 0.0
        g = c.genes
        gen = genetic_diet(g[G_PHOTO], g[G_SAPRO], g[G_CHEMO])
        return 0.5 * sum(abs(a - b) for a, b in zip(c.diet, gen))

    def cell_at(self, x, y):
        if 0 <= x < self.W and 0 <= y < self.H:
            return self.grid[y * self.W + x]
        return None
