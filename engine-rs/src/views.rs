//! Read-only views for front-ends (ADR-0016, G3 P4): `worldsim/views.py`, byte for byte.
//!
//! Pure functions of the world between steps: no RNG draw, nothing written, so the state hash is
//! untouched. The tile word packs each field inside one byte (an RGBA32 texture); the layout is
//! ADR-0016 Decision 1.

use crate::world::{Cell, CellRef, World, EMPTY};
use crate::N_GENES;

/// Kinds of the tile word (1 + the index of Python's `Cell.strategy`).
pub const KIND_EMPTY: u32 = 0;
pub const KIND_PHOTO: u32 = 1;
pub const KIND_SAPRO: u32 = 2;
pub const KIND_PRED: u32 = 3;
pub const KIND_CHEMO: u32 = 4;

/// Number of `TRAITS` (ADR-0014): sex_p, plast_p, hgt_p, armor_p, sense_r.
pub const N_TRAITS: usize = 5;

/// `kind(cell)`: the largest feeding share, the first of (photo, sapro, pred, chemo) on a tie.
pub fn kind(cell: &Cell) -> u32 {
    let p = &cell.pheno;
    let shares = [p.photo, p.sapro, p.pred, p.chemo];
    // `t.index(max(t))`: max keeps the first of equal values, and index finds the first match
    let mut best = 0;
    for (i, &s) in shares.iter().enumerate().skip(1) {
        if s > shares[best] {
            best = i;
        }
    }
    KIND_PHOTO + best as u32
}

/// `energy_level(cell)`: floor(16 * energy / div_thr) clamped to 0..15; NaN gives 0.
pub fn energy_level(cell: &Cell) -> u32 {
    energy_level_of(cell.energy, cell.pheno.div_thr)
}

/// `energy_level_of(energy, div_thr)`; a zero `div_thr` divides as IEEE-754 does (Python's `_ieee_div`).
pub fn energy_level_of(energy: f64, div_thr: f64) -> u32 {
    let q = 16.0 * (energy / div_thr);
    if q.is_nan() || q < 0.0 {
        return 0;
    }
    if q >= 15.0 {
        15
    } else {
        q.floor() as u32
    }
}

/// `chem_level(chem)`: min(3, floor(clip01(chem) * 4)); NaN gives 0.
pub fn chem_level(chem: f64) -> u32 {
    if chem.is_nan() || chem <= 0.0 {
        return 0;
    }
    if chem >= 0.75 {
        3
    } else {
        (chem * 4.0).floor() as u32
    }
}

/// The word of tile `i` (`y * width + x`).
fn tile_word(world: &World, i: usize) -> u32 {
    let mut word =
        (u32::from(world.terrain.rock[i]) << 4) | (chem_level(world.terrain.chem[i]) << 5);
    if let Some(c) = world.cell_at(i % world.width, i / world.width) {
        word |= kind(c) | (u32::from(!c.bonds.is_empty()) << 3);
        word |= energy_level(c) << 8;
        word |= ((c.lineage % (1 << 16)) as u32) << 16;
    }
    word
}

/// Bytes of the tile snapshot: `width * height * 4`.
pub fn tiles_len(world: &World) -> usize {
    world.width * world.height * 4
}

/// `tile_words(world)` into `out`: row-major from the lit surface, each word little-endian.
///
/// # Panics
/// If `out.len() != tiles_len(world)`.
pub fn tile_words(world: &World, out: &mut [u8]) {
    assert_eq!(out.len(), tiles_len(world), "tile buffer size");
    for (i, word) in out.as_chunks_mut::<4>().0.iter_mut().enumerate() {
        *word = tile_word(world, i).to_le_bytes();
    }
}

/// `colony_size(cell)`: cells in the bonded component of the cell `start` refers to, itself included
/// (1 when unbonded). Marks are indexed by slab slot, so the walk does no hashing.
pub(crate) fn colony_size(world: &World, start: CellRef) -> u32 {
    let mut seen = vec![false; world.slab.len()];
    seen[start as usize] = true;
    let mut stack = vec![start];
    let mut size = 1;
    while let Some(cur) = stack.pop() {
        for &r in &world.cell(cur).bonds {
            if !seen[r as usize] {
                seen[r as usize] = true;
                size += 1;
                stack.push(r);
            }
        }
    }
    size
}

/// `cell_record(world, x, y)`: the inspector record (ADR-0016 Decision 2); `None` on an empty tile.
/// The caller checks that (x, y) is inside the world.
#[derive(Debug, Clone, PartialEq)]
pub struct CellRecord {
    pub id: u64,
    pub lineage: u64,
    pub age: u64,
    pub energy: f64,
    pub genes: [f64; N_GENES],
    pub shares: [f64; 4],
    pub traits: [f64; N_TRAITS],
    pub bonds: u32,
    pub colony: u32,
    pub rules: u32,
}

pub fn cell_record(world: &World, x: usize, y: usize) -> Option<CellRecord> {
    if x >= world.width || y >= world.height {
        return None;
    }
    let r = world.grid[y * world.width + x];
    if r == EMPTY {
        return None;
    }
    let c = world.cell(r);
    let p = &c.pheno;
    Some(CellRecord {
        id: c.id,
        lineage: c.lineage,
        age: c.age,
        energy: c.energy,
        genes: c.genes,
        shares: [p.photo, p.sapro, p.pred, p.chemo],
        // sense_r is always 0: the kernel refuses `sense_range` (ADR-0014)
        traits: [c.sex_p, c.plast_p, c.hgt_p, c.armor_p, 0.0],
        bonds: c.bonds.len() as u32,
        colony: colony_size(world, r),
        rules: c.rules.len() as u32,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    // twins of tests/test_views.py::test_energy_level_is_clamped_and_nan_safe and test_edge_values_*
    #[test]
    fn energy_level_edges_match_python() {
        let cases = [
            ((0.0, 20.0), 0),
            ((10.0, 20.0), 8),
            ((19.99, 20.0), 15),
            ((500.0, 20.0), 15),
            ((-3.0, 20.0), 0),
            ((f64::NAN, 20.0), 0),
            ((f64::INFINITY, 20.0), 15),
            ((f64::NEG_INFINITY, 20.0), 0),
            ((5.0, 0.0), 15),
            ((0.0, 0.0), 0),
            ((-5.0, 0.0), 0),
            ((f64::NAN, 0.0), 0),
            ((-0.0, 20.0), 0),
            ((f64::INFINITY, f64::INFINITY), 0),
        ];
        for ((e, d), want) in cases {
            assert_eq!(energy_level_of(e, d), want, "energy {e}, div_thr {d}");
        }
    }

    #[test]
    fn chem_level_edges_match_python() {
        let cases = [
            -1.0,
            0.0,
            0.24,
            0.25,
            0.5,
            0.99,
            1.0,
            7.0,
            f64::NAN,
            f64::INFINITY,
            0.7499,
        ];
        let want = [0, 0, 0, 1, 2, 3, 3, 3, 0, 3, 2];
        for (c, w) in cases.iter().zip(want) {
            assert_eq!(chem_level(*c), w, "chem {c}");
        }
    }

    #[test]
    fn the_key_wraps_and_fills_the_top_byte() {
        let mut world = crate::save::load_world(
            std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("tests/golden/default/start.json.gz"),
        )
        .expect("golden save");
        let r = world.order[0];
        let (x, y) = {
            let c = world.cell(r);
            (c.x, c.y)
        };
        let i = y * world.width + x;
        world.slab[r as usize].lineage = 70_000;
        assert_eq!(tile_word(&world, i) >> 16, 70_000 - 65_536);
        world.slab[r as usize].lineage = 0xFFFF;
        assert_eq!(tile_word(&world, i) >> 24, 0xFF);
        world.slab[r as usize].lineage = u64::from(u32::MAX);
        assert_eq!(tile_word(&world, i) >> 16, 0xFFFF);
    }
}
