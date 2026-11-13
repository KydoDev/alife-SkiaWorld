//! G3 P8 (ADR-0018): what the species tracker costs the step.
//!
//! `cargo run --release --example bench_species -- [steps]` creates the worlds of the `create_default` and
//! `create_volcanic` golden sets (as `ws_world_create` does), steps each twice from the same start, once with
//! the tracker and once without, and prints steps/s and the state hashes (equal: the tracker is an observer).

use std::time::Instant;
use worldsim_core::hash::state_hash;
use worldsim_core::save::config_from_json;
use worldsim_core::world::World;

fn run(world: &mut World, steps: u64) -> f64 {
    let t0 = Instant::now();
    for _ in 0..steps {
        world.step();
    }
    steps as f64 / t0.elapsed().as_secs_f64()
}

fn main() {
    let steps: u64 = std::env::args()
        .nth(1)
        .map_or(2000, |s| s.parse().expect("steps"));
    let golden = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/golden");
    for (name, seed) in [("create_default", 1), ("create_volcanic", 42)] {
        let json = std::fs::read(golden.join(name).join("config.json")).expect("config.json");
        let cfg = config_from_json(&json).expect("config");
        let mut tracked = World::new(cfg.clone(), seed);
        let mut untracked = World::new(cfg, seed);
        untracked.drop_tracker();
        let (a, b) = (run(&mut untracked, steps), run(&mut tracked, steps));
        let same = state_hash(&tracked) == state_hash(&untracked);
        println!(
            "{name:>16}: untracked {a:>7.0} steps/s, tracked {b:>7.0} steps/s ({:+.1}%), population {}, \
             species {}, hashes equal: {same}",
            100.0 * (b / a - 1.0),
            tracked.population(),
            tracked.tracker().map_or(0, |t| t.extant_count()),
        );
    }
}
