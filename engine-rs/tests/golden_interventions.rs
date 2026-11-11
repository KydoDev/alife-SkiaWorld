//! ADR-0013 piece 3: `World::intervene` equals the `play.py` edits. Each case of
//! `scripts/g2_intervention_vectors.py` (`interventions.json` in the golden root, regenerated on Linux by CI)
//! loads a golden start save, applies its actions at their steps and records, after each one, the return value,
//! the state hash, the terrain digest and the render, then one state hash per step.

mod common;

use common::{golden_dir, golden_root, render_digest, terrain_digest};
use serde_json::Value;
use worldsim_core::hash::state_hash;
use worldsim_core::save::load_world;
use worldsim_core::world::{Intervention, World};

const CASES: [&str; 5] = [
    "iv_default",
    "iv_volcanic",
    "iv_reseed",
    "iv_width2",
    "iv_game",
];

fn vectors() -> Value {
    let path = golden_root().join("interventions.json");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).expect("interventions.json")
}

fn u32_of(a: &Value, key: &str) -> u32 {
    u32::try_from(a[key].as_u64().unwrap()).unwrap()
}

fn apply(world: &mut World, name: &str, a: &Value) {
    let iv = Intervention::from_raw(
        u32_of(a, "kind"),
        u32_of(a, "x"),
        u32_of(a, "y"),
        u32_of(a, "radius"),
        a["amount"].as_f64().unwrap(),
    )
    .unwrap_or_else(|e| panic!("{name}: {a}: refused: {e}"));
    let step = a["step"].as_u64().unwrap();
    let ret = world
        .intervene(iv)
        .unwrap_or_else(|e| panic!("{name} at step {step}: {iv:?} refused: {e}"));
    let got = (
        ret,
        state_hash(world),
        terrain_digest(world),
        render_digest(world),
    );
    let want = (
        a["ret"].as_u64().unwrap(),
        a["hash"].as_str().unwrap().to_string(),
        a["terrain"].as_str().unwrap().to_string(),
        a["render"].as_str().unwrap().to_string(),
    );
    assert_eq!(got.0, want.0, "{name} at step {step}: {iv:?} return value");
    assert_eq!(got.1, want.1, "{name} at step {step}: {iv:?} state hash");
    assert_eq!(
        got.2, want.2,
        "{name} at step {step}: {iv:?} terrain digest"
    );
    assert_eq!(got.3, want.3, "{name} at step {step}: {iv:?} render");
}

#[test]
fn interventions_equal_python() {
    let v = vectors();
    let cases = v["cases"].as_array().unwrap();
    let names: Vec<&str> = cases.iter().map(|c| c["name"].as_str().unwrap()).collect();
    assert_eq!(names, CASES);
    for case in cases {
        let name = case["name"].as_str().unwrap();
        let set = case["set"].as_str().unwrap();
        let mut world = load_world(golden_dir(set).join("start.json.gz")).expect("start save");
        let actions = case["actions"].as_array().unwrap();
        let hashes = case["hashes"].as_array().unwrap();
        assert_eq!(
            hashes[0][2].as_str().unwrap(),
            state_hash(&world),
            "{name}: start"
        );
        let last_action = actions.last().unwrap()["step"].as_u64().unwrap();
        let mut next = 0;
        for row in &hashes[1..] {
            while next < actions.len()
                && actions[next]["step"].as_u64().unwrap() == world.step_count
            {
                apply(&mut world, name, &actions[next]);
                next += 1;
            }
            world.step();
            let step = row[0].as_u64().unwrap();
            assert_eq!(world.step_count, step);
            assert_eq!(
                (world.population() as u64, state_hash(&world).as_str()),
                (row[1].as_u64().unwrap(), row[2].as_str().unwrap()),
                "{name}: first divergent step {step}"
            );
        }
        assert_eq!(next, actions.len(), "{name}: every action applied");
        assert!(
            world.step_count >= last_action + 200,
            "{name}: 200 steps after the last action"
        );
    }
}

#[test]
fn the_interventions_vectors_are_not_vacuous() {
    let v = vectors();
    let acts: Vec<(&Value, &Value)> = v["cases"]
        .as_array()
        .unwrap()
        .iter()
        .flat_map(|c| c["actions"].as_array().unwrap().iter().map(move |a| (c, a)))
        .collect();
    let n = |a: &Value, k: &str| a[k].as_u64().unwrap();
    let b = |a: &Value, k: &str| a[k].as_bool().unwrap();
    let need = |what: &str, f: &dyn Fn(&Value, &Value) -> bool| {
        assert!(acts.iter().any(|(c, a)| f(c, a)), "no action shows {what}");
    };
    need("a kill of a bonded cell", &|_, a| {
        n(a, "kind") == 2 && n(a, "ret") > 0 && n(a, "bonded_in_disc") > 0
    });
    need("a raise_rock kill", &|_, a| {
        n(a, "kind") == 3 && n(a, "population") < n(&a["before"], "population")
    });
    for flag in ["has_rock", "has_chem"] {
        need(&format!("{flag} false -> true"), &|_, a| {
            !b(&a["before"], flag) && b(a, flag)
        });
        need(&format!("{flag} true -> false"), &|_, a| {
            b(&a["before"], flag) && !b(a, flag)
        });
    }
    need("a disc wrapping at x = 0", &|_, a| {
        n(a, "x") == 0 && n(a, "radius") > 0
    });
    need("a disc wrapping at x = W-1", &|c, a| {
        n(a, "x") == n(c, "width") - 1 && n(a, "radius") > 0
    });
    need("row 0", &|_, a| n(a, "y") == 0);
    need("row H-1", &|c, a| n(a, "y") == n(c, "height") - 1);
    need("a capped vent on a natural vent", &|_, a| {
        n(a, "kind") == 5 && b(a, "capped_natural")
    });
    need("a nutrient disc over rock", &|_, a| {
        n(a, "kind") == 1 && n(a, "disc_rock") > 0
    });
    need("raise_rock's no-op", &|_, a| {
        n(a, "kind") == 3 && n(a, "ret") == 0
    });
    need("a vent's no-op", &|_, a| {
        n(a, "kind") == 5 && n(a, "ret") == 0
    });
    need("a dig returning 0", &|_, a| {
        n(a, "kind") == 4 && n(a, "ret") == 0
    });
    // an early return leaves the light of the last step, which a fresh update_light would change: the render
    // verdict catches a kernel that refreshes there
    need("a raise_rock no-op with stale light", &|_, a| {
        n(a, "kind") == 3 && b(a, "stale_light")
    });
    need("a vent no-op with stale light", &|_, a| {
        n(a, "kind") == 5 && b(a, "stale_light")
    });
    need("an extinction caused by an edit", &|_, a| {
        n(&a["before"], "population") > 0 && n(a, "population") == 0
    });
}
