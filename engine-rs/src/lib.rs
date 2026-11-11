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
pub mod ffi;
pub mod hash;
pub mod numpy;
pub mod render;
pub mod rng;
pub mod save;
pub mod world;

use std::fmt;

/// Save format version this kernel reads (`worldsim/persistence.py`, ADR-0011).
pub const SAVE_VERSION: u32 = 8;

/// Number of fixed genes per cell (`worldsim/world.py::N_GENES`).
pub const N_GENES: usize = 16;

/// A save the kernel refuses: malformed or hostile content (saves are untrusted input), or a
/// valid save that needs a feature this kernel does not implement yet.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SaveError {
    message: String,
}

/// Longest error message kept, in bytes: a hostile save must not make an error text huge (the
/// JSON parser echoes offending strings, and front-ends copy the message out).
pub const MAX_MESSAGE: usize = 512;

/// Format `value` into at most [`MAX_MESSAGE`] bytes (cut at a char boundary, then "..."),
/// without ever building the full text.
pub(crate) fn bounded(value: impl fmt::Display) -> String {
    struct Capped(String, bool);
    impl fmt::Write for Capped {
        fn write_str(&mut self, s: &str) -> fmt::Result {
            let room = MAX_MESSAGE - self.0.len();
            if s.len() <= room {
                self.0.push_str(s);
                return Ok(());
            }
            let mut cut = room;
            while !s.is_char_boundary(cut) {
                cut -= 1;
            }
            self.0.push_str(&s[..cut]);
            self.1 = true;
            Err(fmt::Error) // stop formatting: the rest is dropped
        }
    }
    let mut out = Capped(String::new(), false);
    let _ = fmt::write(&mut out, format_args!("{value}"));
    if out.1 {
        out.0.push_str("...");
    }
    out.0
}

impl SaveError {
    pub(crate) fn new(message: impl Into<String>) -> Self {
        let message = message.into();
        Self {
            message: if message.len() > MAX_MESSAGE {
                bounded(message)
            } else {
                message
            },
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
