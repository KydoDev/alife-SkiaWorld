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
    // flag fields are hashed only when their flag is on (M5)
    let (hgt, defence) = (world.cfg.hgt, world.cfg.defence);
    if hgt {
        h.update(c.hgt_events.to_le_bytes());
        h.update(c.hgt_foreign.to_le_bytes());
    }
    if defence {
        h.update(c.defended.to_le_bytes());
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
        if hgt {
            h.update(cell.hgt_p.to_le_bytes());
        }
        if defence {
            h.update(cell.armor_p.to_le_bytes());
        }
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

/// The first field, in state-hash order, where two worlds differ (`None` if the hashed state
/// is identical). It also compares the flag fields (e.g. `defended`, `armor_p`) when their flag is
/// off, where the hash skips them: equal hashes do not guarantee `None` for hand-made worlds. Used to diagnose a golden mismatch against a Python save of the same step
/// (`scripts/g2_golden.py --dump-step`).
pub fn first_difference(a: &World, b: &World) -> Option<String> {
    let scalars = [
        ("step_count", a.step_count, b.step_count),
        ("next_id", a.next_id, b.next_id),
        ("births", a.counters.births, b.counters.births),
        ("deaths", a.counters.deaths, b.counters.deaths),
        ("kills", a.counters.kills, b.counters.kills),
        (
            "extinctions",
            a.counters.extinctions,
            b.counters.extinctions,
        ),
        ("sex_births", a.counters.sex_births, b.counters.sex_births),
        ("hgt_events", a.counters.hgt_events, b.counters.hgt_events),
        (
            "hgt_foreign",
            a.counters.hgt_foreign,
            b.counters.hgt_foreign,
        ),
        ("defended", a.counters.defended, b.counters.defended),
    ];
    if let Some((name, x, y)) = scalars.iter().find(|(_, x, y)| x != y) {
        return Some(format!("{name}: {x} vs {y}"));
    }
    let (ra, rb) = (a.rng.state(), b.rng.state());
    if let Some(i) = (0..ra.0.len()).find(|&i| ra.0.get(i) != rb.0.get(i)) {
        return Some(format!("rng word {i}"));
    }
    if ra.1.map(f64::to_bits) != rb.1.map(f64::to_bits) {
        return Some(format!("rng gauss_next: {:?} vs {:?}", ra.1, rb.1));
    }
    if a.organic.len() != b.organic.len() {
        return Some("organic field size".to_string());
    }
    if let Some(i) =
        (0..a.organic.len()).find(|&i| a.organic[i].to_bits() != b.organic[i].to_bits())
    {
        let (x, y) = (i % a.width, i / a.width);
        return Some(format!(
            "organic[{y}, {x}]: {:e} vs {:e}",
            a.organic[i], b.organic[i]
        ));
    }
    if a.population() != b.population() {
        return Some(format!(
            "population: {} vs {}",
            a.population(),
            b.population()
        ));
    }
    for (k, (ca, cb)) in a.cells().zip(b.cells()).enumerate() {
        let bonds = |w: &World, c: &crate::world::Cell| -> Vec<u64> {
            c.bonds.iter().map(|&r| w.cell(r).id).collect()
        };
        let field = if ca.id != cb.id {
            "id"
        } else if (ca.x, ca.y) != (cb.x, cb.y) {
            "position"
        } else if ca.energy.to_bits() != cb.energy.to_bits() {
            "energy"
        } else if ca.age != cb.age {
            "age"
        } else if ca
            .genes
            .iter()
            .zip(&cb.genes)
            .any(|(p, q)| p.to_bits() != q.to_bits())
        {
            "genes"
        } else if ca.lineage != cb.lineage {
            "lineage"
        } else if bonds(a, ca) != bonds(b, cb) {
            "bonds"
        } else if ca.sex_p.to_bits() != cb.sex_p.to_bits() {
            "sex_p"
        } else if ca.hgt_p.to_bits() != cb.hgt_p.to_bits() {
            "hgt_p"
        } else if ca.armor_p.to_bits() != cb.armor_p.to_bits() {
            "armor_p"
        } else {
            continue;
        };
        return Some(format!("cell {k} (id {} vs {}): {field}", ca.id, cb.id));
    }
    None
}
