//! M1c: the kernel loads the golden start saves and their state hash equals Python's step-0 row
//! of `hashes.csv`; malformed saves are refused with an error, never a panic.

mod common;

use common::{golden_dir, hashes, GOLDEN_SETS};
use flate2::read::GzDecoder;
use serde_json::{json, Value};
use std::io::Read;
use worldsim_core::hash::state_hash;
use worldsim_core::save::{load_world, world_from_gzip, world_from_json, world_from_value};

#[test]
fn start_save_hash_matches_python() {
    for set in GOLDEN_SETS {
        let world = load_world(golden_dir(set).join("start.json.gz"))
            .unwrap_or_else(|e| panic!("{set}: {e}"));
        let (step, population, hash) = hashes(set).remove(0);
        assert_eq!(world.step_count, step, "{set}: step");
        assert_eq!(world.population() as u64, population, "{set}: population");
        assert_eq!(state_hash(&world), hash, "{set}: step-0 state hash");
    }
}

#[test]
fn volcanic_save_has_terrain() {
    let world = load_world(golden_dir("volcanic").join("start.json.gz")).expect("volcanic save");
    assert!(world.terrain.rock.iter().any(|&r| r));
    assert!(world.terrain.chem.iter().any(|&c| c > 0.0));
    assert!(world.cfg.day_amplitude > 0.0);
}

/// The default golden save as JSON, for the mutation tests below.
fn base_save() -> Value {
    let gz = std::fs::read(golden_dir("default").join("start.json.gz")).expect("default save");
    let mut text = String::new();
    GzDecoder::new(gz.as_slice())
        .read_to_string(&mut text)
        .expect("gzip");
    serde_json::from_str(&text).expect("json")
}

fn refused(save: &Value, expected: &str) {
    match world_from_value(save) {
        Ok(_) => panic!("save accepted, expected an error containing {expected:?}"),
        Err(e) => assert!(
            e.message().contains(expected),
            "error {:?} does not mention {expected:?}",
            e.message()
        ),
    }
}

fn with(edit: impl FnOnce(&mut Value)) -> Value {
    let mut save = base_save();
    edit(&mut save);
    save
}

#[test]
fn malformed_saves_are_refused() {
    let first_cell = |s: &mut Value| s["cells"][0].clone();
    let cases: Vec<(Value, &str)> = vec![
        (json!([1, 2]), "not a WorldSim save"),
        (
            with(|s| s["format"] = json!("other")),
            "not a WorldSim save",
        ),
        (
            with(|s| s["version"] = json!(5)),
            "unsupported save version 5",
        ),
        (
            with(|s| s["config"]["warp_drive"] = json!(1)),
            "unknown key \"warp_drive\"",
        ),
        (
            with(|s| {
                s["config"].as_object_mut().unwrap().remove("shade");
            }),
            "missing key \"shade\"",
        ),
        (
            with(|s| s["config"]["shade"] = json!(1.5)),
            "shade = 1.5 is outside",
        ),
        (
            with(|s| s["config"]["width"] = json!(160.0)),
            "width must be int",
        ),
        (
            with(|s| s["config"]["sensing"] = json!(1)),
            "sensing must be bool",
        ),
        (
            with(|s| s["config"]["div_min"] = json!(100.0)),
            "div_min/mut_min",
        ),
        (with(|s| s["config"]["sex"] = json!(true)), "sex is on"),
        (
            with(|s| s["counters"]["births"] = json!(-1)),
            "invalid counter \"births\"",
        ),
        (
            with(|s| s["counters"]["kills"] = json!(true)),
            "invalid counter \"kills\"",
        ),
        (
            with(|s| {
                s["rng"]["internal"]
                    .as_array_mut()
                    .unwrap()
                    .pop()
                    .map(|_| ())
                    .unwrap()
            }),
            "625",
        ),
        (
            with(|s| s["rng"]["internal"][624] = json!(625)),
            "index 625",
        ),
        (
            with(|s| s["rng"]["internal"][0] = json!(1u64 << 32)),
            "exceeds 32 bits",
        ),
        (
            with(|s| s["organic"][0][0] = json!(-1.0)),
            "finite and non-negative",
        ),
        (
            with(|s| {
                s["organic"].as_array_mut().unwrap().pop();
            }),
            "does not match",
        ),
        (
            with(|s| s["terrain"] = json!({"rock": [], "chem": [], "sun": []})),
            "terrain maps",
        ),
        (with(|s| s["terrain"] = json!(3)), "invalid terrain"),
        (with(|s| s["cells"][0] = json!([1, 2, 3])), "13 fields"),
        (with(|s| s["cells"][0][1] = json!(160)), "outside the grid"),
        (with(|s| s["cells"][0][2] = json!(-1)), "outside the grid"),
        (
            with(|s| {
                let c = first_cell(s);
                s["cells"][1][1] = c[1].clone();
                s["cells"][1][2] = c[2].clone();
            }),
            "occupied",
        ),
        (with(|s| s["cells"][0][5][3] = json!(1.01)), "invalid cell"),
        (with(|s| s["cells"][0][5] = json!([0.5])), "invalid cell"),
        (with(|s| s["cells"][0][3] = json!("lots")), "invalid cell"),
        (
            with(|s| {
                let id = first_cell(s)[0].clone();
                s["cells"][1][0] = id;
            }),
            "invalid cell",
        ),
        (
            with(|s| s["cells"][0][9] = json!([[0.5, 0.5, 0.5, 0.5]])),
            "rule genes",
        ),
        (with(|s| s["cells"][0][10] = json!(0.5)), "sex_p"),
        (with(|s| s["cells"][0][11] = json!(0.5)), "plast_p"),
        (with(|s| s["cells"][0][12] = json!([0.3, 0.3, 0.4])), "diet"),
        (
            with(|s| s["cells"][0][8] = json!([999_999_999])),
            "bonded to missing",
        ),
        (
            with(|s| {
                let id = first_cell(s)[0].clone();
                s["cells"][0][8] = json!([id]);
            }),
            "self or duplicate",
        ),
        (
            with(|s| {
                let id = s["cells"][1][0].clone();
                s["cells"][0][8] = json!([id]);
                s["cells"][1][8] = json!([]);
            }),
            "not symmetric",
        ),
    ];
    for (save, expected) in &cases {
        refused(save, expected);
    }
}

#[test]
fn bad_bytes_are_refused() {
    assert!(world_from_json(b"{not json").is_err());
    assert!(world_from_json(b"[1e400]").is_err());
    assert!(world_from_gzip(b"not gzip at all", 1 << 20).is_err());
    let gz = std::fs::read(golden_dir("default").join("start.json.gz")).expect("default save");
    assert!(
        world_from_gzip(&gz[..gz.len() / 2], 1 << 30).is_err(),
        "truncated gzip"
    );
    let err = world_from_gzip(&gz, 1000).expect_err("decompressed size cap");
    assert!(err.message().contains("more than 1000 bytes"));
}

/// Cheap fuzzing: corrupt single bytes of the decompressed JSON; every outcome must be an
/// `Ok` or an `Err`, never a panic (the test harness would report a panic as a failure).
#[test]
fn corrupted_json_never_panics() {
    let text = serde_json::to_vec(&base_save()).expect("json");
    let mut state: u64 = 0x2545_f491_4f6c_dd1d;
    let mut next = move || {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        state
    };
    let alphabet = b"0123456789-.,:[]{}\"e truefalsn";
    for _ in 0..300 {
        let mut bytes = text.clone();
        let at = (next() % bytes.len() as u64) as usize;
        bytes[at] = alphabet[(next() % alphabet.len() as u64) as usize];
        let _ = world_from_json(&bytes);
    }
}
