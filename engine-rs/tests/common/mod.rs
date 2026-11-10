//! Shared helpers for the golden-vector tests.

use std::path::PathBuf;

/// The golden sets checked by every test.
pub const GOLDEN_SETS: [&str; 2] = ["default", "volcanic"];

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
