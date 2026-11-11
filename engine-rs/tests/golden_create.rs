//! ADR-0012 piece 4: `World::new(cfg, seed)` equals Python's `World(cfg, seed)`: the step-0 state hash on every
//! case of `scripts/g2_create_vectors.py` (`create.json` in the golden root), and every hashed step of the
//! creation sets, which the kernel builds itself instead of loading their start save.

mod common;

use common::{golden_dir, golden_root, hashes, CREATE_SETS};
use serde_json::Value;
use worldsim_core::config::Config;
use worldsim_core::hash::{first_difference, state_hash};
use worldsim_core::save::load_world;
use worldsim_core::world::World;

fn read_json(path: std::path::PathBuf) -> Value {
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).expect("json")
}

#[test]
fn creation_equals_python_at_step_zero() {
    let v = read_json(golden_root().join("create.json"));
    let cases = v["cases"].as_array().unwrap();
    assert!(cases.len() >= 50);
    let mut failures = Vec::new();
    for c in cases {
        let name = c["name"].as_str().unwrap();
        let seed: u64 = c["seed"].as_str().unwrap().parse().unwrap();
        let cfg = Config::from_json(c["config"].as_object().unwrap())
            .unwrap_or_else(|e| panic!("config of {name}: {e}"));
        let world = World::new(cfg, seed);
        if state_hash(&world) != c["hash"].as_str().unwrap() {
            failures.push(format!("{name}, seed {seed}"));
        }
        assert_eq!(
            world.population() as u64,
            c["population"].as_u64().unwrap(),
            "{name}"
        );
        assert_eq!(world.next_id, c["next_id"].as_u64().unwrap(), "{name}");
    }
    assert!(failures.is_empty(), "step-0 hash differs: {failures:?}");
    // not vacuous: rock, vents, every founder draw, no founders and more founders than free tiles
    let any = |f: &dyn Fn(&Value) -> bool| cases.iter().any(f);
    assert!(any(
        &|c| c["rock_tiles"].as_u64().unwrap() > 0 && c["vents"].as_bool().unwrap()
    ));
    for flag in ["sex", "plasticity", "hgt", "defence", "open_genome"] {
        assert!(any(
            &|c| c["config"][flag].as_bool().unwrap() && c["population"].as_u64().unwrap() > 0
        ));
    }
    assert!(any(&|c| c["population"].as_u64().unwrap() == 0));
    assert!(any(&|c| {
        let free = c["free_tiles"].as_u64().unwrap();
        c["config"]["initial_cells"].as_u64().unwrap() > free
            && c["population"].as_u64().unwrap() == free
    }));
}

#[test]
fn creation_sets_step_like_python() {
    for set in CREATE_SETS {
        let dir = golden_dir(set);
        let seed = read_json(dir.join("rng.json"))["seed"]
            .as_u64()
            .expect("seed");
        let loaded = load_world(dir.join("start.json.gz")).expect("start save");
        let mut world = World::new(loaded.cfg.clone(), seed);
        assert_eq!(world.step_count, 0, "{set}: creation sets start at step 0");
        if let Some(diff) = first_difference(&loaded, &world) {
            panic!("{set}: World::new differs from the start save: {diff}");
        }
        let rows = hashes(set);
        assert_eq!(rows[0].2, state_hash(&world), "{set}: step 0");
        for (step, population, hash) in &rows[1..] {
            world.step();
            assert_eq!(world.step_count, *step);
            assert_eq!(
                (world.population() as u64, state_hash(&world).as_str()),
                (*population, hash.as_str()),
                "{set}: first divergent step {step}"
            );
        }
    }
}
