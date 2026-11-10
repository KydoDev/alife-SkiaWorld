//! M2: stepping the kernel from the golden start save reproduces Python's state hash at every
//! one of the 1000 steps, on both golden sets (bit-for-bit, no tolerance).
//!
//! The comparison is against the golden set made on the same OS (`WORLDSIM_GOLDEN_DIR`, see
//! `tests/common`). On a mismatch the test reports the first divergent step and, when Python's
//! save of that step is present (`scripts/g2_golden.py --dump-step N --out target/g2-dumps/<set>`),
//! the first field that differs, in state-hash order.

mod common;

use common::{golden_dir, hashes, GOLDEN_SETS};
use std::path::PathBuf;
use worldsim_core::hash::{first_difference, state_hash};
use worldsim_core::save::load_world;
use worldsim_core::world::World;

/// The first differing field against Python's dump of `step`, or how to produce that dump.
fn diagnose(set: &str, step: u64, world: &World) -> String {
    let dump = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("target/g2-dumps")
        .join(set)
        .join(format!("step_{step}.json.gz"));
    match load_world(&dump) {
        Ok(python) => match first_difference(world, &python) {
            Some(field) => format!("first differing field (kernel vs Python): {field}"),
            None => "no hashed field differs from the dump: is it from another golden set?".into(),
        },
        Err(_) => format!(
            "for the first differing field, run scripts/g2_golden.py with this set's arguments plus --dump-step {step} --out engine-rs/target/g2-dumps/{set}"
        ),
    }
}

/// Steps `set` through its `hashes.csv`; returns the first divergent step, if any.
fn first_divergence(set: &str) -> Option<String> {
    let mut world =
        load_world(golden_dir(set).join("start.json.gz")).unwrap_or_else(|e| panic!("{set}: {e}"));
    let rows = hashes(set);
    assert_eq!(state_hash(&world), rows[0].2, "{set}: start hash (M1c)");
    for (step, population, hash) in &rows[1..] {
        world.step();
        let got = state_hash(&world);
        if world.step_count != *step || got != *hash {
            return Some(format!(
                "{set}: first divergent step {step} (kernel at step {}, population {} vs Python {population}; hash {} vs {}); {}",
                world.step_count,
                world.population(),
                &got[..12],
                &hash[..12],
                diagnose(set, *step, &world)
            ));
        }
    }
    None
}

#[test]
fn stepping_matches_python_for_every_golden_step() {
    let failures: Vec<String> = GOLDEN_SETS
        .iter()
        .filter_map(|set| first_divergence(set))
        .collect();
    assert!(failures.is_empty(), "{}", failures.join("\n"));
}

#[test]
fn first_difference_names_the_field() {
    let world = load_world(golden_dir("default").join("start.json.gz")).expect("default save");
    assert_eq!(first_difference(&world, &world.clone()), None);
    let mut other = world.clone();
    other.organic[3 * world.width + 5] += 1e-12;
    let found = first_difference(&world, &other).expect("organic differs");
    assert!(found.starts_with("organic[3, 5]"), "{found}");
    let mut other = world.clone();
    other.step();
    assert!(first_difference(&world, &other)
        .expect("stepped")
        .starts_with("step_count"));
}
