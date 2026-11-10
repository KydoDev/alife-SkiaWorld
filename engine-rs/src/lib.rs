//! WorldSim core: the Rust reference kernel of the engine (G2, ADR-0008).
//!
//! The Python engine in `worldsim/` is the reference. This crate must reproduce it
//! step by step: same iteration order, same CPython `random.Random` stream, same
//! IEEE-754 arithmetic. Progress and verification criteria: `docs/G2_PLAN.md`.
//!
//! Milestone M1a: crate skeleton and access to the golden vectors only.

/// Save format version this kernel reads (`worldsim/persistence.py`, ADR-0009).
pub const SAVE_VERSION: u32 = 6;

/// Number of fixed genes per cell (`worldsim/world.py::N_GENES`).
pub const N_GENES: usize = 16;
