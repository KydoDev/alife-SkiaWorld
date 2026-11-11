//! Shared helpers for the golden-vector tests.

use std::path::PathBuf;

/// The golden sets checked by every test.
#[allow(dead_code)] // the terrain vectors test uses only the root
pub const GOLDEN_SETS: [&str; 20] = [
    "default",
    "volcanic",
    "defence",
    "defence_neutral",
    "hgt",
    "hgt_neutral",
    "plasticity",
    "plastic_neutral",
    "sex",
    "sex_neutral",
    "sensing",
    "sensing_volcanic",
    "open_genome",
    "rules_neutral",
    "combined",
    "combined_reseed",
    "combined_width2",
    "open_genome_unsensed",
    "create_default",
    "create_volcanic",
];

/// The golden sets hashed from creation (step 0): the kernel also builds them with `World::new`.
#[allow(dead_code)] // not every test crate that includes this module uses it
pub const CREATE_SETS: [&str; 2] = ["create_default", "create_volcanic"];

/// Root of the golden sets: `$WORLDSIM_GOLDEN_DIR` if set, else the committed
/// `tests/golden/` (the Windows reference). CI sets it to sets regenerated on Linux, since
/// `gauss` and the stepped hashes depend on the platform maths library (docs/G2_PLAN.md).
pub fn golden_root() -> PathBuf {
    match std::env::var_os("WORLDSIM_GOLDEN_DIR") {
        Some(dir) => PathBuf::from(dir),
        None => PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/golden"),
    }
}

/// Directory of one golden set under [`golden_root`].
pub fn golden_dir(set: &str) -> PathBuf {
    golden_root().join(set)
}

/// The rows of a set's `hashes.csv`: `(step, population, hash)`, the start row first.
#[allow(dead_code)] // not every test crate that includes this module uses it
pub fn hashes(set: &str) -> Vec<(u64, u64, String)> {
    let path = golden_dir(set).join("hashes.csv");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    text.lines()
        .skip(1)
        .map(|line| {
            let f: Vec<&str> = line.split(',').collect();
            assert_eq!(f.len(), 3, "bad hashes.csv row: {line}");
            (
                f[0].parse().expect("step"),
                f[1].parse().expect("population"),
                f[2].to_string(),
            )
        })
        .collect()
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// ADR-0012's terrain digest with the live organic field (ADR-0013): SHA-256 of rock as `u8`, then chem, sun
/// and organic as little-endian `f64`, row-major. The state hash covers neither rock nor chem.
#[allow(dead_code)] // not every test crate that includes this module uses it
pub fn terrain_digest(world: &worldsim_core::world::World) -> String {
    use sha2::{Digest, Sha256};
    let mut h = Sha256::new();
    let t = &world.terrain;
    h.update(t.rock.iter().map(|&r| u8::from(r)).collect::<Vec<u8>>());
    for values in [&t.chem, &t.sun, &world.organic] {
        for v in values.iter() {
            h.update(v.to_le_bytes());
        }
    }
    hex(&h.finalize())
}

/// SHA-256 of the kernel's `render_rgb` (the interventions vectors store Python's render this way).
#[allow(dead_code)] // not every test crate that includes this module uses it
pub fn render_digest(world: &worldsim_core::world::World) -> String {
    use sha2::{Digest, Sha256};
    let mut rgb = vec![0u8; worldsim_core::render::rgb_len(world)];
    worldsim_core::render::render_rgb(world, &mut rgb);
    hex(&Sha256::digest(&rgb))
}
