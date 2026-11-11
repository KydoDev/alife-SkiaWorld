//! G2 milestone M3: single-threaded throughput of the reference kernel (docs/G2_PLAN.md).
//!
//! `python scripts/g2_bench.py --out target/bench` writes the worlds and the Python baseline; then
//! `cargo run --release --example bench -- target/bench [steps]` steps each save (default 1000 steps),
//! checks the state hash against Python's after the steps Python timed (the kernel must still be
//! exact on large worlds), and prints cell-updates per second against the M3 target.

use serde_json::Value;
use std::time::Instant;
use worldsim_core::hash::state_hash;
use worldsim_core::save::load_world;

/// M3 target: 30 000 cells x 60 steps/s, single-threaded.
const TARGET: f64 = 1.8e6;

fn main() {
    let mut args = std::env::args().skip(1);
    let dir = std::path::PathBuf::from(args.next().unwrap_or_else(|| "target/bench".into()));
    let steps: u64 = args.next().map_or(1000, |s| s.parse().expect("steps"));
    let report: Value = serde_json::from_str(
        &std::fs::read_to_string(dir.join("bench.json"))
            .expect("bench.json (run scripts/g2_bench.py)"),
    )
    .expect("bench.json");
    println!(
        "target: {TARGET:.1e} cell-updates/s (30k cells x 60 steps/s), {steps} steps per world"
    );
    for w in report["worlds"].as_array().expect("worlds") {
        let name = w["name"].as_str().expect("name");
        let py_steps = w["steps"].as_u64().expect("steps");
        let py_rate = w["updates_per_s"].as_f64().expect("rate");
        let mut world = load_world(dir.join(format!("{name}.json.gz"))).expect("save");
        let (mut updates, mut step_time) = (0u64, 0.0f64);
        let mut checked = "not reached";
        for s in 1..=steps.max(py_steps) {
            updates += world.population() as u64;
            let t0 = Instant::now();
            world.step();
            step_time += t0.elapsed().as_secs_f64();
            if s == py_steps {
                checked = if state_hash(&world) == w["final_hash"].as_str().expect("hash") {
                    "equal"
                } else {
                    "DIFFERENT"
                };
            }
        }
        let rate = updates as f64 / step_time;
        let mean_pop = updates as f64 / steps.max(py_steps) as f64;
        println!(
            "{name:>4}: {rate:>12.0} cell-updates/s ({:.0}x Python, {:.2}x target), {:.0} steps/s, \
             mean population {mean_pop:.0}, final {}; hash after {py_steps} steps vs Python: {checked}",
            rate / py_rate,
            rate / TARGET,
            steps.max(py_steps) as f64 / step_time,
            world.population()
        );
    }
}
