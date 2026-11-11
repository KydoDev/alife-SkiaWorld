//! Shared helpers for the golden-vector tests.

use std::path::PathBuf;

/// The golden sets checked by every test.
pub const GOLDEN_SETS: [&str; 14] = [
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
];

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
