//! World state and the step (`worldsim/world.py`): the default flags (G2 M2) plus, from M5, the
//! optional flags ported so far (`defence`, `hgt`, `plasticity`). Other flags are refused by the loader.
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

/// Traits derived from the genes at birth (`Cell.express`); with `plasticity` on, the feeding
/// shares and their `_k` powers follow the acclimated diet (`Cell.apply_diet`).
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Phenotype {
    /// Feeding shares (`Cell.photo` ...): they colour the cell in the render.
    pub photo: f64,
    pub sapro: f64,
    pub pred: f64,
    pub chemo: f64,
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

/// The heritable flag propensities a cell is born with (Python's `Cell(...)` keywords); each is 0
/// while its flag is off.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Traits {
    pub plast_p: f64,
    pub hgt_p: f64,
    pub armor_p: f64,
}

/// `genetic_diet`: the genetic split of the non-predatory share among photo / sapro / chemo.
fn genetic_diet(photo: f64, sapro: f64, chemo: f64) -> [f64; 3] {
    let s = photo + sapro + chemo;
    if s > 0.0 {
        [photo / s, sapro / s, chemo / s]
    } else {
        [1.0 / 3.0; 3]
    }
}

impl Phenotype {
    /// The genetic part of `Cell.express(cfg)`, then the flag upkeep terms in Python's order
    /// (`plast_p`, `hgt_p`, `armor_p`). The diet is applied by [`Cell::express`].
    pub fn express(g: &[f64; N_GENES], t: Traits, cfg: &Config) -> Self {
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
        let mut upkeep = cfg.base_cost + cfg.pred_upkeep * pred + cfg.move_upkeep * mv;
        if cfg.plasticity {
            upkeep += cfg.plastic_upkeep * t.plast_p;
        }
        if cfg.hgt {
            upkeep += cfg.hgt_upkeep * t.hgt_p;
        }
        if cfg.defence {
            upkeep += cfg.defence_upkeep * t.armor_p;
        }
        Self {
            photo,
            sapro,
            pred,
            chemo,
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
            upkeep,
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
    /// F5b rate of diet acclimation; 0 unless `plasticity` is on.
    pub plast_p: f64,
    /// F5b acclimated (photo, sapro, chemo) split; all zero unless `plasticity` is on (Python: `()`).
    pub diet: [f64; 3],
    /// F5c propensity to copy a neighbour's gene; 0 unless `hgt` is on.
    pub hgt_p: f64,
    /// F5e armour: share of attacks the cell can repel; 0 unless `defence` is on.
    pub armor_p: f64,
    pub alive: bool,
    pub pheno: Phenotype,
}

impl Cell {
    /// A newborn (age 0, no bonds), phenotype expressed from its genes and flag traits.
    #[allow(clippy::too_many_arguments)] // mirrors Python's Cell(...) constructor
    pub fn new(
        id: u64,
        x: usize,
        y: usize,
        energy: f64,
        genes: [f64; N_GENES],
        lineage: u64,
        traits: Traits,
        cfg: &Config,
    ) -> Self {
        let mut cell = Self {
            id,
            x,
            y,
            energy,
            age: 0,
            genes,
            lineage,
            bonds: Vec::new(),
            sex_p: 0.0,
            plast_p: traits.plast_p,
            diet: [0.0; 3],
            hgt_p: traits.hgt_p,
            armor_p: traits.armor_p,
            alive: true,
            pheno: Phenotype::default(),
        };
        cell.express(cfg);
        cell
    }

    /// The traits the cell was born with (they never change during its life).
    pub fn traits(&self) -> Traits {
        Traits {
            plast_p: self.plast_p,
            hgt_p: self.hgt_p,
            armor_p: self.armor_p,
        }
    }

    /// `Cell.express(cfg)`: phenotype from the genes; with `plasticity` on the diet is reset to
    /// the genetic split and applied (also after a gene transfer, as in Python).
    pub fn express(&mut self, cfg: &Config) {
        self.pheno = Phenotype::express(&self.genes, self.traits(), cfg);
        if cfg.plasticity {
            let ph = &self.pheno;
            self.diet = genetic_diet(ph.photo, ph.sapro, ph.chemo);
            self.apply_diet(cfg);
        }
    }

    /// `Cell.apply_diet` (F5b): feeding shares from the diet; the predation share stays genetic.
    pub fn apply_diet(&mut self, cfg: &Config) {
        let g = &self.genes;
        // all four feeding genes at 0: the cell cannot feed (Python's truthiness: -0.0 is zero)
        let feeds = g[G_PHOTO] != 0.0 || g[G_SAPRO] != 0.0 || g[G_PRED] != 0.0 || g[G_CHEMO] != 0.0;
        let non_pred = if feeds { 1.0 - self.pheno.pred } else { 0.0 };
        let [p, s, ch] = self.diet;
        let e = cfg.spec_exp;
        let ph = &mut self.pheno;
        ph.photo = non_pred * p;
        ph.sapro = non_pred * s;
        ph.chemo = non_pred * ch;
        ph.photo_k = ph.photo.powf(e);
        ph.sapro_k = ph.sapro.powf(e);
        ph.chemo_k = ph.chemo.powf(e);
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
    /// F5c: genes copied from a neighbour, and those from another lineage (hashed only when
    /// `hgt` is on).
    pub hgt_events: u64,
    pub hgt_foreign: u64,
    /// F5e: attacks repelled by armour (hashed only when `defence` is on).
    pub defended: u64,
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

    /// The flag draws of a founder (seeded or immigrant), after its genes, in Python's keyword
    /// order: `plast_p`, `hgt_p`, `armor_p`.
    fn founder_traits(&mut self) -> Traits {
        let mut draw = |on: bool| if on { self.rng.random() } else { 0.0 };
        let plast_p = draw(self.cfg.plasticity);
        let hgt_p = draw(self.cfg.hgt);
        let armor_p = draw(self.cfg.defence);
        Traits {
            plast_p,
            hgt_p,
            armor_p,
        }
    }

    /// `World.acclimate` (F5b): move the diet towards the split of what each diet would yield on
    /// this tile at full specialisation. No RNG; with nothing to gain here the diet stays put.
    fn acclimate(&mut self, r: CellRef, light_here: f64, organic_here: f64, chem_here: f64) {
        let cfg = &self.cfg;
        let yp = cfg.photo_gain * light_here;
        let ys = cfg.sapro_eff * py_min(organic_here, cfg.sapro_rate);
        let yc = cfg.chemo_gain * chem_here;
        let total = yp + ys + yc;
        if total <= 0.0 {
            return;
        }
        let c = &mut self.slab[r as usize];
        let rate = c.plast_p * cfg.plastic_rate;
        let [p, s, ch] = c.diet;
        c.diet = [
            p + rate * (yp / total - p),
            s + rate * (ys / total - s),
            ch + rate * (yc / total - ch),
        ];
        c.apply_diet(cfg);
    }

    /// `min(1.0, max(0.0, p + gauss(0, sigma)))`: a propensity inherited with a mutation step.
    fn offspring_propensity(&mut self, p: f64, sigma: f64) -> f64 {
        py_min(1.0, py_max(0.0, p + self.rng.gauss(0.0, sigma)))
    }

    /// `World.transfer_gene` (F5c): copy one random gene from a random neighbour (any lineage,
    /// bonded or not), then re-express. The genome changes for life and is inherited.
    fn transfer_gene(&mut self, r: CellRef) {
        let (x, y) = (self.slab[r as usize].x, self.slab[r as usize].y);
        let (tiles, n) = self.neighbors(x, y);
        let mut donors = [EMPTY; 8];
        let mut k = 0;
        for &(nx, ny) in &tiles[..n] {
            let o = self.grid[ny * self.width + nx];
            if o != EMPTY {
                donors[k] = o;
                k += 1;
            }
        }
        if k == 0 {
            return;
        }
        let donor = *self.rng.choice(&donors[..k]) as usize;
        let gene = self.rng.randrange(N_GENES as u64) as usize;
        let (value, donor_lineage) = (self.slab[donor].genes[gene], self.slab[donor].lineage);
        let cfg = &self.cfg;
        let c = &mut self.slab[r as usize];
        c.genes[gene] = value;
        c.express(cfg);
        let foreign = donor_lineage != c.lineage;
        self.counters.hgt_events += 1;
        if foreign {
            self.counters.hgt_foreign += 1;
        }
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
            let traits = self.founder_traits();
            let cell = Cell::new(
                id,
                i % self.width,
                i / self.width,
                self.cfg.initial_energy,
                genes,
                id,
                traits,
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

    /// `World.step()` for the flags the kernel runs (no species tracker). One function on
    /// purpose, like Python's: the per-cell loop is the hot path and its order of operations is
    /// what has to match. Flag blocks draw from the RNG only when their flag is on.
    pub fn step(&mut self) {
        let cfg = self.cfg.clone();
        let w = self.width;
        let (defence_on, armour) = (cfg.defence, cfg.defence && !cfg.defence_neutral);
        let (hgt_on, transfer) = (cfg.hgt, cfg.hgt && !cfg.hgt_neutral);
        let (plastic_on, plastic) = (cfg.plasticity, cfg.plasticity && !cfg.plastic_neutral);
        self.update_light(self.step_count + 1);

        let mut order = std::mem::take(&mut self.order);
        self.rng.shuffle(&mut order);
        let mut newborns: Vec<CellRef> = Vec::new();

        for &r in &order {
            let ri = r as usize;
            if !self.slab[ri].alive {
                continue;
            }
            self.slab[ri].age += 1;
            // 0: F5c horizontal transfer, before feeding so the whole turn uses one phenotype
            if transfer && self.rng.random() < self.slab[ri].hgt_p * cfg.hgt_rate {
                self.transfer_gene(r);
            }
            // 1-3 (F5b): the diet first acclimates to this tile
            if plastic && self.slab[ri].plast_p > 0.0 {
                let tile = self.slab[ri].y * w + self.slab[ri].x;
                let chem_here = if self.has_chem {
                    self.terrain.chem[tile]
                } else {
                    0.0
                };
                self.acclimate(r, self.light[tile], self.organic[tile], chem_here);
            }
            let (x, y, ph) = {
                let c = &self.slab[ri];
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
                    // F5e: the armour may repel the attack; then nobody gains or loses energy
                    if armour
                        && self.rng.random()
                            < self.slab[prey as usize].armor_p * cfg.defence_strength
                    {
                        self.counters.defended += 1;
                    } else {
                        let food = py_max(self.slab[prey as usize].energy, 0.0) + cfg.body_cost;
                        self.slab[ri].energy += cfg.pred_eff * food;
                        self.kill(prey, (1.0 - cfg.pred_eff) * food);
                        self.counters.kills += 1;
                    }
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
                    let parent = c.traits();
                    let genes = self.mutate(&parent_genes, ph.mut_sigma);
                    // `offspring_plast_p`, `offspring_hgt_p`, then `offspring_armor_p` (Python's order)
                    let plast_p = if plastic_on {
                        self.offspring_propensity(parent.plast_p, ph.mut_sigma)
                    } else {
                        0.0
                    };
                    let hgt_p = if hgt_on {
                        self.offspring_propensity(parent.hgt_p, ph.mut_sigma)
                    } else {
                        0.0
                    };
                    let armor_p = if defence_on {
                        self.offspring_propensity(parent.armor_p, ph.mut_sigma)
                    } else {
                        0.0
                    };
                    let id = self.new_id();
                    let traits = Traits {
                        plast_p,
                        hgt_p,
                        armor_p,
                    };
                    let child =
                        self.alloc(Cell::new(id, sx, sy, child_e, genes, lineage, traits, &cfg));
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
                    let traits = self.founder_traits();
                    let cell = Cell::new(
                        id,
                        i % w,
                        i / w,
                        cfg.initial_energy,
                        genes,
                        id,
                        traits,
                        &cfg,
                    );
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
