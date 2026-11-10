//! The G2 state hash (`docs/G2_PLAN.md`, "State hash"; Python: `scripts/g2_golden.py::state_hash`).
//!
//! SHA-256 over the dynamic state, little-endian, byte-for-byte the same definition as the
//! Python one. Observer state (species, tracker) and derived fields (light, phenotype) are
//! excluded: they are recomputed, and hashing them would only hide where a difference started.

use crate::world::World;
use sha2::{Digest, Sha256};

/// Lower-case hex SHA-256 of the world state.
pub fn state_hash(world: &World) -> String {
    hex(&state_digest(world))
}

/// Raw SHA-256 of the world state.
pub fn state_digest(world: &World) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(world.step_count.to_le_bytes());
    h.update(world.next_id.to_le_bytes());
    let c = &world.counters;
    for n in [c.births, c.deaths, c.kills, c.extinctions, c.sex_births] {
        h.update(n.to_le_bytes());
    }
    let (words, gauss_next) = world.rng.state();
    for w in words {
        h.update(w.to_le_bytes()); // 624 MT words, then the position index
    }
    match gauss_next {
        None => {
            h.update([0u8]);
            h.update(0.0f64.to_le_bytes());
        }
        Some(z) => {
            h.update([1u8]);
            h.update(z.to_le_bytes());
        }
    }
    for v in &world.organic {
        h.update(v.to_le_bytes());
    }
    h.update((world.population() as u64).to_le_bytes());
    for cell in world.cells() {
        h.update(cell.id.to_le_bytes());
        h.update((cell.x as u32).to_le_bytes());
        h.update((cell.y as u32).to_le_bytes());
        h.update(cell.energy.to_le_bytes());
        h.update(cell.age.to_le_bytes());
        for g in cell.genes {
            h.update(g.to_le_bytes());
        }
        h.update(cell.lineage.to_le_bytes());
        h.update((cell.bonds.len() as u64).to_le_bytes());
        for &b in &cell.bonds {
            h.update(world.cell(b).id.to_le_bytes());
        }
        h.update(cell.sex_p.to_le_bytes());
    }
    h.finalize().into()
}

fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for &b in bytes {
        s.push(DIGITS[(b >> 4) as usize] as char);
        s.push(DIGITS[(b & 15) as usize] as char);
    }
    s
}
