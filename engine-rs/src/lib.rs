//! WorldSim core: the Rust reference kernel of the engine (G2, ADR-0008).
//!
//! The Python engine in `worldsim/` is the reference. This crate must reproduce it
//! step by step: same iteration order, same CPython `random.Random` stream, same
//! IEEE-754 arithmetic. Progress and verification criteria: `docs/G2_PLAN.md`.
//!
//! Milestones so far: M1a (crate skeleton, golden vectors), M1b ([`rng`], the CPython
//! `random.Random` stream), M1c ([`save`], loading a save, and [`hash`], the state hash) and
//! M2 ([`world`], `World::step` for the default flags, bit-exact against Python).

pub mod config;
pub mod hash;
pub mod rng;
pub mod save;
pub mod world;

use std::fmt;

/// Save format version this kernel reads (`worldsim/persistence.py`, ADR-0010).
pub const SAVE_VERSION: u32 = 8;

/// Number of fixed genes per cell (`worldsim/world.py::N_GENES`).
pub const N_GENES: usize = 16;

/// A save the kernel refuses: malformed or hostile content (saves are untrusted input), or a
/// valid save that needs a feature this kernel does not implement yet.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SaveError {
    message: String,
}

impl SaveError {
    pub(crate) fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }

    /// The human-readable reason.
    pub fn message(&self) -> &str {
        &self.message
    }
}

impl fmt::Display for SaveError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for SaveError {}
