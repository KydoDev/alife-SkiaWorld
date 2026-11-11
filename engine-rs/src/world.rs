//! World state and the step (`worldsim/world.py`), default flags only (G2 milestone M2).
//!
//! Cells live in a slab (`World::slab`) and are referred to by slot ([`CellRef`]), never by
//! pointer; `World::order` is Python's `World.cells` list (its order is part of the state: the
//! step shuffles it) and each cell's `bonds` keeps Python's dict insertion order.
//!
//! Bit-exactness with Python rests on doing the same IEEE-754 operations in the same order:
//! every expression below keeps Python's left-to-right evaluation, `min`/`max` keep Python's
//! tie rules (`max(a, b)` returns `a` unless `b > a`), and random draws happen exactly where
//! Python draws (short-circuited `and` included). Transcendentals (`pow`, `exp`, `sin`,
//! `gauss`) go through the platform maths library, as CPython and numpy do.

use crate::config::Config;
use crate::rng::PyRandom;
use crate::N_GENES;

/// Index of a cell in [`World::slab`].
pub type CellRef = u32;

/// Marks an empty grid tile.
pub const EMPTY: CellRef = CellRef::MAX;

// Gene indices (`worldsim/world.py`).
pub(crate) const G_PHOTO: usize = 0;
pub(crate) const G_SAPRO: usize = 1;
pub(crate) const G_PRED: usize = 2;
const G_MOVE: usize = 3;
const G_DIV: usize = 4;
const G_CHILD: usize = 5;
const G_ATTACH: usize = 6;
const G_SHARE: usize = 7;
const G_MUT: usize = 8;
pub(crate) const G_CHEMO: usize = 9;

/// `NEIGH8`: neighbour offsets in Python's order (it fixes which tile a `choice` picks).
const NEIGH8: [(isize, isize); 8] = [
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
];

/// Traits derived from the genes once at birth (`Cell.express`, default flags).
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Phenotype {
    pub photo_k: f64,
    pub sapro_k: f64,
    pub pred_k: f64,
    pub chemo_k: f64,
    pub move_p: f64,
    pub div_thr: f64,
    pub child_frac: f64,
    pub attach: f64,
    pub share: f64,
    pub mut_sigma: f64,
    pub upkeep: f64,
}

impl Phenotype {
    /// `Cell.express(cfg)` with sensing, open genome and plasticity off.
    pub fn express(g: &[f64; N_GENES], cfg: &Config) -> Self {
        let mut s = g[G_PHOTO] + g[G_SAPRO] + g[G_PRED] + g[G_CHEMO];
        if s == 0.0 {
            s = 1e-9; // Python: `... or 1e-9`
        }
        let (photo, sapro, pred, chemo) = (
            g[G_PHOTO] / s,
            g[G_SAPRO] / s,
            g[G_PRED] / s,
            g[G_CHEMO] / s,
        );
        let e = cfg.spec_exp;
        let mv = g[G_MOVE];
        Self {
            photo_k: photo.powf(e),
            sapro_k: sapro.powf(e),
            pred_k: pred.powf(e),
            chemo_k: chemo.powf(e),
            move_p: mv,
            div_thr: cfg.div_min + g[G_DIV] * (cfg.div_max - cfg.div_min),
            child_frac: 0.2 + 0.6 * g[G_CHILD],
            attach: g[G_ATTACH],
            share: 0.5 * g[G_SHARE],
            mut_sigma: cfg.mut_min + g[G_MUT] * (cfg.mut_max - cfg.mut_min),
            upkeep: cfg.base_cost + cfg.pred_upkeep * pred + cfg.move_upkeep * mv,
        }
    }
}

/// One cell (`worldsim/world.py::Cell`).
#[derive(Debug, Clone, PartialEq)]
pub struct Cell {
    pub id: u64,
    pub x: usize,
    pub y: usize,
    pub energy: f64,
    pub age: u64,
    pub genes: [f64; N_GENES],
    pub lineage: u64,
    /// Bonded cells, in insertion order (energy sharing iterates them).
    pub bonds: Vec<CellRef>,
    /// F5a mating propensity; always 0 while `sex` is off (kept for the state hash).
    pub sex_p: f64,
    pub alive: bool,
    pub pheno: Phenotype,
}

impl Cell {
    /// A newborn (age 0, no bonds), phenotype expressed from its genes.
    pub fn new(
        id: u64,
        x: usize,
        y: usize,
        energy: f64,
        genes: [f64; N_GENES],
        lineage: u64,
        cfg: &Config,
    ) -> Self {
        Self {
            id,
            x,
            y,
            energy,
            age: 0,
            genes,
            lineage,
            bonds: Vec::new(),
            sex_p: 0.0,
            alive: true,
            pheno: Phenotype::express(&genes, cfg),
        }
    }
}

/// Static terrain maps (`worldsim/terrain.py::Terrain`), row-major `(H, W)` except `sun` (`W`).
#[derive(Debug, Clone, PartialEq)]
pub struct Terrain {
    pub rock: Vec<bool>,
    pub chem: Vec<f64>,
    pub sun: Vec<f64>,
}

impl Terrain {
    /// The flat, vent-free world (a save stores `terrain: null` for it).
    pub fn flat(width: usize, height: usize) -> Self {
        Self {
            rock: vec![false; width * height],
            chem: vec![0.0; width * height],
            sun: vec![1.0; width],
        }
    }
}

/// The simulation counters, in the order of the state hash.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Counters {
    pub births: u64,
    pub deaths: u64,
    pub kills: u64,
    pub extinctions: u64,
    pub sex_births: u64,
}

/// A world: configuration, RNG, fields and cells.
#[derive(Debug, Clone)]
pub struct World {
    pub cfg: Config,
    pub width: usize,
    pub height: usize,
    pub step_count: u64,
    pub next_id: u64,
    pub counters: Counters,
    pub rng: PyRandom,
    /// Organic matter, row-major `(H, W)`.
    pub organic: Vec<f64>,
    pub terrain: Terrain,
    /// Light of the current step (recomputed at its start), row-major `(H, W)`.
    pub light: Vec<f64>,
    pub(crate) slab: Vec<Cell>,
    pub(crate) order: Vec<CellRef>,
    pub(crate) grid: Vec<CellRef>,
    free_slots: Vec<CellRef>,
    /// Depth attenuation x sun x "no rock above" (`World.base_light`).
    base_light: Vec<f64>,
    /// `shade ** k` for `k` cells above, `k = 0..H` (`np.power(shade, above)`, tabulated).
    shade_pow: Vec<f64>,
    pub(crate) has_rock: bool,
    pub(crate) has_chem: bool,
}

impl World {
    /// An empty world on `terrain` (`World(..., populate=False)` plus `set_terrain`); the
    /// caller restores counters and places cells.
    pub fn from_parts(cfg: Config, terrain: Terrain, rng: PyRandom, organic: Vec<f64>) -> Self {
        let (w, h) = (cfg.w(), cfg.h());
        // depth = light_max * exp(-rows / light_depth); base = depth[:, None] * sun[None, :] * lit
        let mut base_light = vec![0.0; w * h];
        let mut lit = vec![true; w];
        for y in 0..h {
            let depth = cfg.light_max * (-(y as f64) / cfg.light_depth).exp();
            for (x, lit_x) in lit.iter_mut().enumerate() {
                let i = y * w + x;
                *lit_x &= !terrain.rock[i]; // rocks are opaque: dark at and below the first one
                base_light[i] = depth * terrain.sun[x] * if *lit_x { 1.0 } else { 0.0 };
            }
        }
        let shade_pow = (0..=h).map(|k| cfg.shade.powf(k as f64)).collect();
        Self {
            width: w,
            height: h,
            step_count: 0,
            next_id: 0,
            counters: Counters::default(),
            rng,
            organic,
            has_rock: terrain.rock.iter().any(|&r| r),
            has_chem: terrain.chem.iter().any(|&c| c != 0.0),
            terrain,
            light: base_light.clone(),
            slab: Vec::new(),
            order: Vec::new(),
            grid: vec![EMPTY; w * h],
            free_slots: Vec::new(),
            base_light,
            shade_pow,
            cfg,
        }
    }

    /// Number of living cells (`len(World.cells)` between steps).
    pub fn population(&self) -> usize {
        self.order.len()
    }

    /// Cells in list order (Python's `World.cells`).
    pub fn cells(&self) -> impl Iterator<Item = &Cell> {
        self.order.iter().map(|&r| &self.slab[r as usize])
    }

    /// The cell a reference points to.
    pub fn cell(&self, r: CellRef) -> &Cell {
        &self.slab[r as usize]
    }

    /// The cell on tile `(x, y)`, if any.
    pub fn cell_at(&self, x: usize, y: usize) -> Option<&Cell> {
        if x >= self.width || y >= self.height {
            return None;
        }
        match self.grid[y * self.width + x] {
            EMPTY => None,
            r => Some(&self.slab[r as usize]),
        }
    }

    // ------------------------------------------------------------------ helpers

    fn new_id(&mut self) -> u64 {
        self.next_id += 1;
        self.next_id
    }

    fn alloc(&mut self, cell: Cell) -> CellRef {
        match self.free_slots.pop() {
            Some(r) => {
                self.slab[r as usize] = cell;
                r
            }
            None => {
                self.slab.push(cell);
                (self.slab.len() - 1) as CellRef
            }
        }
    }

    /// `World._place`: put a new cell on the grid and at the end of the cell list.
    fn place(&mut self, cell: Cell) {
        let tile = cell.y * self.width + cell.x;
        let r = self.alloc(cell);
        self.grid[tile] = r;
        self.order.push(r);
    }

    fn random_genes(&mut self) -> [f64; N_GENES] {
        let mut g = [0.0; N_GENES];
        for v in &mut g {
            *v = self.rng.random();
        }
        g
    }

    /// `World.neighbors`: the in-grid neighbour tiles, x toroidal, in `NEIGH8` order.
    fn neighbors(&self, x: usize, y: usize) -> ([(usize, usize); 8], usize) {
        let (w, h) = (self.width as isize, self.height as isize);
        let mut out = [(0, 0); 8];
        let mut n = 0;
        for (dx, dy) in NEIGH8 {
            let ny = y as isize + dy;
            if 0 <= ny && ny < h {
                out[n] = ((x as isize + dx).rem_euclid(w) as usize, ny as usize);
                n += 1;
            }
        }
        (out, n)
    }

    /// `World.random_empty_neighbor`.
    fn random_empty_neighbor(&mut self, x: usize, y: usize) -> Option<(usize, usize)> {
        let (tiles, n) = self.neighbors(x, y);
        let mut free = [(0, 0); 8];
        let mut k = 0;
        for &(nx, ny) in &tiles[..n] {
            let i = ny * self.width + nx;
            if self.grid[i] == EMPTY && !(self.has_rock && self.terrain.rock[i]) {
                free[k] = (nx, ny);
                k += 1;
            }
        }
        (k > 0).then(|| *self.rng.choice(&free[..k]))
    }

    /// `World.random_prey`: a random neighbour that is not bonded to `c`.
    fn random_prey(&mut self, c: CellRef) -> Option<CellRef> {
        let cell = &self.slab[c as usize];
        let (tiles, n) = self.neighbors(cell.x, cell.y);
        let mut prey = [EMPTY; 8];
        let mut k = 0;
        for &(nx, ny) in &tiles[..n] {
            let o = self.grid[ny * self.width + nx];
            if o != EMPTY && !cell.bonds.contains(&o) {
                prey[k] = o;
                k += 1;
            }
        }
        (k > 0).then(|| *self.rng.choice(&prey[..k]))
    }

    /// `World.mutate`: `min(1.0, max(0.0, v + gauss(0, sigma)))` per gene, in order.
    fn mutate(&mut self, genes: &[f64; N_GENES], sigma: f64) -> [f64; N_GENES] {
        let mut out = [0.0; N_GENES];
        for (o, &v) in out.iter_mut().zip(genes) {
            *o = py_min(1.0, py_max(0.0, v + self.rng.gauss(0.0, sigma)));
        }
        out
    }

    /// `World.kill`: remove from the grid and from its partners' bonds, return organic matter.
    fn kill(&mut self, c: CellRef, organic_amount: f64) {
        let cell = &mut self.slab[c as usize];
        cell.alive = false;
        let tile = cell.y * self.width + cell.x;
        let bonds = std::mem::take(&mut cell.bonds);
        self.grid[tile] = EMPTY;
        for b in bonds {
            let partner = &mut self.slab[b as usize].bonds;
            if let Some(pos) = partner.iter().position(|&o| o == c) {
                partner.remove(pos); // dict.pop keeps the order of the others
            }
        }
        if organic_amount > 0.0 {
            self.organic[tile] += organic_amount;
        }
        self.counters.deaths += 1;
    }

    /// `World.seed_population(n)`: `n` random cells on shuffled free tiles.
    fn seed_population(&mut self, n: usize) {
        let mut free: Vec<usize> = (0..self.grid.len())
            .filter(|&i| self.grid[i] == EMPTY && !self.terrain.rock[i])
            .collect();
        self.rng.shuffle(&mut free);
        free.truncate(n);
        for i in free {
            let id = self.new_id();
            let genes = self.random_genes();
            let cell = Cell::new(
                id,
                i % self.width,
                i / self.width,
                self.cfg.initial_energy,
                genes,
                id,
                &self.cfg,
            );
            self.place(cell);
        }
    }

    // ------------------------------------------------------------------ fields

    /// `World.light_factor(t)`: day/night x season multiplier, a pure function of the step.
    pub fn light_factor(&self, t: u64) -> f64 {
        let cfg = &self.cfg;
        if cfg.day_amplitude == 0.0 && cfg.season_amplitude == 0.0 {
            return 1.0;
        }
        let two_pi = 2.0 * std::f64::consts::PI;
        let mut f = 1.0;
        if cfg.day_amplitude != 0.0 {
            f *= 1.0 + cfg.day_amplitude * (two_pi * t as f64 / cfg.day_length as f64).sin();
        }
        if cfg.season_amplitude != 0.0 {
            f *= 1.0 + cfg.season_amplitude * (two_pi * t as f64 / cfg.year_length as f64).sin();
        }
        f
    }

    /// `World.update_light` at step `now`: base light x `shade ** (cells above)` x factor.
    pub(crate) fn update_light(&mut self, now: u64) {
        let w = self.width;
        let f = self.light_factor(now);
        let mut above = vec![0usize; w];
        for (i, light) in self.light.iter_mut().enumerate() {
            let x = i % w;
            *light = self.base_light[i] * self.shade_pow[above[x]];
            if f != 1.0 {
                *light *= f;
            }
            if self.grid[i] != EMPTY {
                above[x] += 1;
            }
        }
    }

    /// `World.update_organic`: diffusion (x toroidal, y closed), sinking, decay.
    fn update_organic(&mut self) {
        let (w, h) = (self.width, self.height);
        let cfg = &self.cfg;
        let old = self.organic.clone();
        let o = &mut self.organic;
        for y in 0..h {
            let up = y.saturating_sub(1);
            let down = if y + 1 < h { y + 1 } else { y };
            for x in 0..w {
                let i = y * w + x;
                let left = old[y * w + (x + w - 1) % w];
                let right = old[y * w + (x + 1) % w];
                let mean = (old[up * w + x] + old[down * w + x] + left + right) * 0.25;
                o[i] = old[i] + cfg.organic_diffusion * (mean - old[i]);
            }
        }
        // moved = o[:-1] * sink (zero above rock); o[:-1] -= moved; o[1:] += moved
        let mut moved = vec![0.0; w * (h - 1)];
        for (i, m) in moved.iter_mut().enumerate() {
            *m = o[i] * cfg.organic_sink;
            if self.has_rock && self.terrain.rock[i + w] {
                *m *= 0.0;
            }
        }
        for (i, &m) in moved.iter().enumerate() {
            o[i] -= m;
        }
        for (i, &m) in moved.iter().enumerate() {
            o[i + w] += m;
        }
        let keep = 1.0 - cfg.organic_decay;
        for v in o.iter_mut() {
            *v *= keep;
        }
    }

    // ------------------------------------------------------------------ step

    /// `World.step()` for the default flags (sensing, open genome, sex, plasticity off; no
    /// species tracker). One function on purpose, like Python's: the per-cell loop is the hot
    /// path and its order of operations is what has to match.
    pub fn step(&mut self) {
        let cfg = self.cfg.clone();
        let w = self.width;
        self.update_light(self.step_count + 1);

        let mut order = std::mem::take(&mut self.order);
        self.rng.shuffle(&mut order);
        let mut newborns: Vec<CellRef> = Vec::new();

        for &r in &order {
            let ri = r as usize;
            if !self.slab[ri].alive {
                continue;
            }
            let (x, y, ph) = {
                let c = &mut self.slab[ri];
                c.age += 1;
                (c.x, c.y, c.pheno)
            };
            let tile = y * w + x;

            // 1-3: metabolism and feeding
            let mut e = self.slab[ri].energy - ph.upkeep;
            if ph.photo_k > 0.0 {
                e += cfg.photo_gain * ph.photo_k * self.light[tile];
            }
            if ph.sapro_k > 0.0 {
                let avail = self.organic[tile];
                if avail > 0.0 {
                    let take = py_min(avail, cfg.sapro_rate * ph.sapro_k);
                    self.organic[tile] = avail - take;
                    e += cfg.sapro_eff * take;
                }
            }
            if self.has_chem && ph.chemo_k > 0.0 {
                e += cfg.chemo_gain * ph.chemo_k * self.terrain.chem[tile];
            }
            self.slab[ri].energy = e;

            // 4: predation
            if ph.pred_k > 0.0 && self.rng.random() < ph.pred_k {
                if let Some(prey) = self.random_prey(r) {
                    let food = py_max(self.slab[prey as usize].energy, 0.0) + cfg.body_cost;
                    self.slab[ri].energy += cfg.pred_eff * food;
                    self.kill(prey, (1.0 - cfg.pred_eff) * food);
                    self.counters.kills += 1;
                }
            }

            // 5: movement (unbonded cells only): a random walk
            if self.slab[ri].bonds.is_empty() && ph.move_p > 0.0 && self.rng.random() < ph.move_p {
                if let Some((nx, ny)) = self.random_empty_neighbor(x, y) {
                    self.grid[tile] = EMPTY;
                    self.grid[ny * w + nx] = r;
                    let c = &mut self.slab[ri];
                    c.x = nx;
                    c.y = ny;
                    c.energy -= cfg.move_cost;
                }
            }

            // 6: energy sharing within the colony, in bond insertion order
            if ph.share > 0.0 {
                for k in 0..self.slab[ri].bonds.len() {
                    let b = self.slab[ri].bonds[k] as usize;
                    let diff = self.slab[ri].energy - self.slab[b].energy;
                    if diff > 0.0 {
                        let t = diff * ph.share * 0.5;
                        self.slab[ri].energy -= t;
                        self.slab[b].energy += t;
                    }
                }
            }

            // 8a: death
            let (energy, age) = (self.slab[ri].energy, self.slab[ri].age);
            if energy <= 0.0 || age > cfg.max_age as u64 {
                self.kill(
                    r,
                    cfg.decomp_fraction * (py_max(energy, 0.0) + cfg.body_cost),
                );
                continue;
            }

            // 7: division
            if energy >= ph.div_thr {
                let (cx, cy) = (self.slab[ri].x, self.slab[ri].y);
                if let Some((sx, sy)) = self.random_empty_neighbor(cx, cy) {
                    let c = &mut self.slab[ri];
                    c.energy -= cfg.body_cost;
                    let child_e = c.energy * ph.child_frac;
                    c.energy -= child_e;
                    let (parent_genes, lineage) = (c.genes, c.lineage);
                    let genes = self.mutate(&parent_genes, ph.mut_sigma);
                    let id = self.new_id();
                    let child = self.alloc(Cell::new(id, sx, sy, child_e, genes, lineage, &cfg));
                    self.grid[sy * w + sx] = child;
                    newborns.push(child);
                    self.counters.births += 1;
                    if self.rng.random() < ph.attach
                        && (self.slab[ri].bonds.len() as i64) < cfg.max_bonds
                    {
                        self.slab[ri].bonds.push(child);
                        self.slab[child as usize].bonds.push(r);
                    }
                }
            }
        }

        // Survivors in list order, then the surviving newborns; dead slots are reused later.
        let mut next = Vec::with_capacity(order.len() + newborns.len());
        for r in order.into_iter().chain(newborns) {
            if self.slab[r as usize].alive {
                next.push(r);
            } else {
                self.free_slots.push(r);
            }
        }
        self.order = next;
        self.update_organic();
        self.step_count += 1;

        if cfg.immigration_rate > 0.0 {
            let mut k = cfg.immigration_rate.trunc() as u64; // int(rate)
            if self.rng.random() < cfg.immigration_rate - k as f64 {
                k += 1;
            }
            let tiles = (self.width * self.height) as u64;
            for _ in 0..k {
                let i = self.rng.randrange(tiles) as usize;
                if self.grid[i] == EMPTY && !self.terrain.rock[i] {
                    let id = self.new_id();
                    let genes = self.random_genes();
                    let cell = Cell::new(id, i % w, i / w, cfg.initial_energy, genes, id, &cfg);
                    self.place(cell);
                }
            }
        }

        if self.order.is_empty() && cfg.reseed_on_extinction {
            self.counters.extinctions += 1;
            self.seed_population(cfg.initial_cells as usize);
        }
    }
}

/// Python's `max(a, b)`: `a` unless `b > a` (decides the sign of a zero result).
fn py_max(a: f64, b: f64) -> f64 {
    if b > a {
        b
    } else {
        a
    }
}

/// Python's `min(a, b)`: `a` unless `b < a`.
fn py_min(a: f64, b: f64) -> f64 {
    if b < a {
        b
    } else {
        a
    }
}
