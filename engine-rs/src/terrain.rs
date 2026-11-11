//! Procedural terrain (`worldsim/terrain.py`), reproduced bit for bit (ADR-0012 piece 3).
//!
//! The terrain has its own random stream, `random.Random(f"worldsim-terrain-{seed}")`, never the
//! world's. The maths follows the Python line for line: libm `sin` and `exp` (`f64::sin`/`exp`
//! call the platform library, as `math.sin`/`math.exp` do), numpy's pairwise `mean`, `np.rint`
//! (ties to even), and a `sqrt` of an exact integer. `vent_plume` is shared with the `add_vent`
//! intervention (ADR-0013).

use crate::config::Config;
use crate::numpy::numpy_mean;
use crate::rng::PyRandom;
use crate::world::Terrain;
use std::f64::consts::PI;

/// The `Config` fields procedural terrain reads.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TerrainParams {
    pub width: usize,
    pub height: usize,
    pub organic_init: f64,
    pub rock_fraction: f64,
    pub vent_count: i64,
    pub vent_strength: f64,
    pub vent_radius: f64,
}

impl TerrainParams {
    pub fn from_config(cfg: &Config) -> Self {
        Self {
            width: cfg.w(),
            height: cfg.h(),
            organic_init: cfg.organic_init,
            rock_fraction: cfg.rock_fraction,
            vent_count: cfg.vent_count,
            vent_strength: cfg.vent_strength,
            vent_radius: cfg.vent_radius,
        }
    }
}

/// `generate_terrain(cfg, seed)`: the static maps and the initial organic field (row-major `(H, W)`).
/// Defaults give the flat, vent-free world without touching any random stream.
pub fn generate_terrain(p: &TerrainParams, seed: u64) -> (Terrain, Vec<f64>) {
    let (w, h) = (p.width, p.height);
    let mut terrain = Terrain::flat(w, h);
    let mut organic = vec![p.organic_init; w * h];
    if p.rock_fraction <= 0.0 && p.vent_count <= 0 {
        return (terrain, organic);
    }
    let mut rng = PyRandom::from_seed_str(&format!("worldsim-terrain-{seed}"));
    let heights = seabed_heights(w, h, p.rock_fraction, &mut rng);
    for y in 0..h {
        for (x, &top) in heights.iter().enumerate() {
            terrain.rock[y * w + x] = y >= h - top;
        }
    }
    terrain.chem = vent_field(&terrain.rock, w, h, p, &mut rng);
    for (o, &rock) in organic.iter_mut().zip(&terrain.rock) {
        if rock {
            *o = 0.0;
        }
    }
    (terrain, organic)
}

/// Rock height per column (`seabed_heights`): an x-periodic ridge averaging `rock_fraction * H`,
/// never reaching row 0.
fn seabed_heights(w: usize, h: usize, rock_fraction: f64, rng: &mut PyRandom) -> Vec<usize> {
    if rock_fraction <= 0.0 {
        return vec![0; w];
    }
    let mut profile = vec![1.0f64; w];
    for k in [1u32, 2, 3, 5] {
        let k = f64::from(k);
        let scale = 2.0 * PI * k;
        // rng.uniform(0, 2*pi) = 0 + (2*pi - 0) * random()
        let phase = 2.0 * PI * rng.random();
        let amplitude = 0.6 / k;
        for (x, v) in profile.iter_mut().enumerate() {
            *v += amplitude * (scale * x as f64 / w as f64 + phase).sin();
        }
    }
    for v in profile.iter_mut() {
        if *v < 0.0 {
            *v = 0.0; // np.clip(profile, 0.0, None)
        }
    }
    let factor = rock_fraction * h as f64 / numpy_mean(&profile);
    let top = (h - 1) as f64;
    profile
        .iter()
        // np.clip(np.rint(profile * factor), 0, H - 1).astype(int64); the mean is > 0 for every
        // width >= 2, so the values are finite
        .map(|&v| (v * factor).round_ties_even().clamp(0.0, top) as usize)
        .collect()
}

/// `vent_field`: chemical energy around `vent_count` vents on top of the seabed, zero on rock.
fn vent_field(
    rock: &[bool],
    w: usize,
    h: usize,
    p: &TerrainParams,
    rng: &mut PyRandom,
) -> Vec<f64> {
    let mut chem = vec![0.0; w * h];
    if p.vent_count <= 0 || p.vent_strength <= 0.0 {
        return chem;
    }
    let table = PlumeTable::new(w, h, p.vent_strength, p.vent_radius);
    for _ in 0..p.vent_count {
        let vx = rng.randrange(w as u64) as usize;
        // first water tile above the rock; row 0 is never rock, so the first solid row is >= 1
        let first_solid = (0..h).find(|&y| rock[y * w + vx]).unwrap_or(h);
        let vy = first_solid - 1;
        for (y, row) in chem.chunks_exact_mut(w).enumerate() {
            for (x, c) in row.iter_mut().enumerate() {
                *c += table.at(x, y, vx, vy); // chem += vent_plume(...)
            }
        }
    }
    for (c, &r) in chem.iter_mut().zip(rock) {
        if r {
            *c = 0.0;
        }
    }
    chem
}

/// `vent_plume(H, W, vx, vy, strength, radius)`: `strength * exp(-dist / radius)` with `dist` the
/// toroidal-in-x distance from the vent, row-major `(H, W)`. `(vx, vy)` must lie in the grid.
pub fn vent_plume(
    h: usize,
    w: usize,
    vx: usize,
    vy: usize,
    strength: f64,
    radius: f64,
) -> Vec<f64> {
    assert!(vx < w && vy < h, "vent ({vx}, {vy}) outside a {w}x{h} grid");
    let table = PlumeTable::new(w, h, strength, radius);
    let mut plume = Vec::with_capacity(w * h);
    for y in 0..h {
        plume.extend((0..w).map(|x| table.at(x, y, vx, vy)));
    }
    plume
}

/// The plume value for every `(|dy|, dx)` with `dx` the toroidal x offset (`<= W/2`): the value
/// depends only on `dx*dx + dy*dy`, so it is the one Python computes per distinct distance, and
/// `exp` runs about `H * W / 2` times however many vents there are.
struct PlumeTable {
    half: usize,
    width: usize,
    values: Vec<f64>,
}

impl PlumeTable {
    fn new(w: usize, h: usize, strength: f64, radius: f64) -> Self {
        let half = w / 2;
        let mut values = Vec::with_capacity(h * (half + 1));
        for dy in 0..h as u64 {
            for dx in 0..=half as u64 {
                // integer sum, exact in f64 (< 2^53), then one correctly rounded sqrt
                let dist = ((dx * dx + dy * dy) as f64).sqrt();
                values.push(strength * (-dist / radius).exp());
            }
        }
        Self {
            half,
            width: w,
            values,
        }
    }

    fn at(&self, x: usize, y: usize, vx: usize, vy: usize) -> f64 {
        let adx = x.abs_diff(vx);
        let dx = adx.min(self.width - adx);
        self.values[y.abs_diff(vy) * (self.half + 1) + dx]
    }
}
