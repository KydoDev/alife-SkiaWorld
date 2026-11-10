//! World state: grid, cells, fields (`worldsim/world.py`).
//!
//! Cells live in a slab (`World::slab`) and are referred to by slot ([`CellRef`]), never by
//! pointer; `World::order` is Python's `World.cells` list (its order is part of the state: the
//! step shuffles it) and each cell's `bonds` keeps Python's dict insertion order.

use crate::config::Config;
use crate::rng::PyRandom;
use crate::N_GENES;

/// Index of a cell in [`World::slab`].
pub type CellRef = u32;

/// Marks an empty grid tile.
pub const EMPTY: CellRef = CellRef::MAX;

/// The saved state of one cell (`worldsim/world.py::Cell`; phenotype fields are derived).
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
    pub(crate) slab: Vec<Cell>,
    pub(crate) order: Vec<CellRef>,
    pub(crate) grid: Vec<CellRef>,
}

impl World {
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
}
