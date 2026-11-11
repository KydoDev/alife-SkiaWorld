//! M1c: the kernel loads the golden start saves and their state hash equals Python's step-0 row
//! of `hashes.csv`; malformed or hostile saves are refused with an error, never a panic.

mod common;

use common::{golden_dir, hashes, GOLDEN_SETS};
use flate2::read::GzDecoder;
use serde_json::{json, Value};
use std::io::Read;
use worldsim_core::hash::state_hash;
use worldsim_core::save::{load_world, world_from_gzip, world_from_json};

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
    set_save("default")
}

/// A golden start save as JSON.
fn set_save(set: &str) -> Value {
    let gz = std::fs::read(golden_dir(set).join("start.json.gz")).expect("golden save");
    let mut text = String::new();
    GzDecoder::new(gz.as_slice())
        .read_to_string(&mut text)
        .expect("gzip");
    serde_json::from_str(&text).expect("json")
}

fn load(save: &Value) -> Result<worldsim_core::world::World, worldsim_core::SaveError> {
    world_from_json(&serde_json::to_vec(save).expect("json"))
}

fn with(edit: impl FnOnce(&mut Value)) -> Value {
    let mut save = base_save();
    edit(&mut save);
    save
}

/// Index of a cell row with no bonds, and its id.
fn lonely_cell(save: &Value) -> (usize, Value) {
    let cells = save["cells"].as_array().expect("cells");
    let i = cells
        .iter()
        .position(|c| c[8].as_array().is_some_and(Vec::is_empty))
        .expect("an unbonded cell");
    (i, cells[i][0].clone())
}

#[test]
fn the_unmodified_base_save_loads() {
    load(&base_save()).expect("base save");
}

#[test]
fn malformed_saves_are_refused() {
    const BAD: &str = "not a valid save file";
    let cases: Vec<(Value, &str)> = vec![
        (json!([1, 2]), BAD),
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
        (with(|s| s["config"]["shade"] = json!([0.7])), BAD),
        (
            with(|s| s["config"]["div_min"] = json!(100.0)),
            "div_min/mut_min",
        ),
        (
            with(|s| s["config"]["sensing"] = json!(true)),
            "sensing is on",
        ),
        (
            with(|s| s["config"]["open_genome"] = json!(true)),
            "open_genome is on",
        ),
        (with(|s| s["seed"] = json!(1.5)), BAD),
        (
            with(|s| {
                s.as_object_mut().unwrap().remove("tracker");
            }),
            "missing field `tracker`",
        ),
        (
            with(|s| s["step_count"] = json!(1u64 << 63)),
            "exceeds 2^62",
        ),
        (with(|s| s["next_id"] = json!(3)), "above next_id"),
        (with(|s| s["counters"]["births"] = json!(-1)), BAD),
        (with(|s| s["counters"]["kills"] = json!(true)), BAD),
        (
            with(|s| s["counters"]["deaths"] = json!(u64::MAX)),
            "exceeds 2^62",
        ),
        (with(|s| s["rng"]["version"] = json!(3.0)), BAD),
        (
            with(|s| {
                s["rng"]["internal"].as_array_mut().unwrap().pop();
            }),
            "624 words, expected 625",
        ),
        (
            with(|s| s["rng"]["internal"].as_array_mut().unwrap().push(json!(1))),
            "list longer than 625",
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
            with(|s| {
                s["rng"].as_object_mut().unwrap().remove("gauss_next");
            }),
            "missing field `gauss_next`",
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
            with(|s| s["organic"][0] = json!(vec![0.0; 10_001])),
            "larger than any valid world",
        ),
        (
            with(|s| s["terrain"] = json!({"rock": [], "chem": [], "sun": []})),
            "does not match",
        ),
        (
            with(|s| s["terrain"] = json!({"rock": [[2]], "chem": [], "sun": []})),
            "only 0 and 1",
        ),
        (with(|s| s["terrain"] = json!(3)), BAD),
        (with(|s| s["cells"][0] = json!([1, 2, 3])), BAD),
        (
            with(|s| s["cells"][0].as_array_mut().unwrap().push(json!(0))),
            BAD,
        ),
        (with(|s| s["cells"][0][1] = json!(160)), "outside the grid"),
        (with(|s| s["cells"][0][2] = json!(-1)), BAD),
        (with(|s| s["cells"][0][1] = json!(1.0)), BAD),
        (
            with(|s| {
                let c = s["cells"][0].clone();
                s["cells"][1][1] = c[1].clone();
                s["cells"][1][2] = c[2].clone();
            }),
            "occupied",
        ),
        (with(|s| s["cells"][0][5][3] = json!(1.01)), "invalid cell"),
        (with(|s| s["cells"][0][5] = json!([0.5])), BAD),
        (with(|s| s["cells"][0][3] = json!("lots")), BAD),
        (with(|s| s["cells"][0][4] = json!(u64::MAX)), "exceeds 2^62"),
        (
            with(|s| {
                let id = s["cells"][0][0].clone();
                s["cells"][1][0] = id;
            }),
            "invalid cell",
        ),
        (
            with(|s| s["cells"][0][9] = json!([[0.5, 0.5, 0.5, 0.5]])),
            "list longer than 0",
        ),
        (with(|s| s["cells"][0][10] = json!(0.5)), "sex_p"),
        (with(|s| s["cells"][0][11] = json!(0.5)), "plast_p"),
        (with(|s| s["cells"][0][13] = json!(0.5)), "hgt_p"),
        (with(|s| s["cells"][0][14] = json!(0.5)), "armor_p"),
        (
            with(|s| s["counters"]["hgt_foreign"] = json!(1)),
            "hgt_foreign exceeds hgt_events",
        ),
        (
            with(|s| s["cells"][0][12] = json!([0.3, 0.3, 0.4])),
            "invalid diet",
        ),
        (
            with(|s| s["cells"][0][12] = json!([0.3, 0.3, 0.2, 0.2])),
            "list longer than 3",
        ),
        (
            with(|s| s["cells"][0][8] = json!([999_999_999])),
            "bonded to missing",
        ),
        (
            with(|s| s["cells"][0][8] = json!(vec![1; 9])),
            "list longer than 8",
        ),
        (
            with(|s| {
                let (i, id) = lonely_cell(s);
                s["cells"][i][8] = json!([id]);
            }),
            "self or duplicate",
        ),
        (
            with(|s| {
                let (i, _) = lonely_cell(s);
                let other = if i == 0 { 1 } else { 0 };
                let id = s["cells"][other][0].clone();
                s["cells"][i][8] = json!([id]);
            }),
            "not symmetric",
        ),
    ];
    for (save, expected) in &cases {
        match load(save) {
            Ok(_) => panic!("save accepted, expected an error containing {expected:?}"),
            Err(e) => assert!(
                e.message().contains(expected),
                "error {:?} does not mention {expected:?}",
                e.message()
            ),
        }
    }
}

/// With `defence` (`hgt`) on, `armor_p` (`hgt_p`) must be in [0, 1] (`persistence.py`); the bounds
/// load, values past them do not.
#[test]
fn propensities_are_bounded_when_their_flag_is_on() {
    let armoured = |v: Value| {
        let mut s = set_save("defence");
        s["cells"][0][14] = v;
        load(&s)
    };
    for v in [json!(0.0), json!(-0.0), json!(1.0), json!(0.5)] {
        assert!(armoured(v.clone()).is_ok(), "armor_p {v} refused");
    }
    for v in [json!(1.01), json!(-0.01), json!(true)] {
        let e = armoured(v.clone())
            .err()
            .unwrap_or_else(|| panic!("armor_p {v} accepted"));
        assert!(
            e.message().contains("armor_p") || e.message().contains("invalid"),
            "{v}: {}",
            e.message()
        );
    }
    let hgt = |v: Value| {
        let mut s = set_save("hgt");
        s["cells"][0][13] = v;
        load(&s)
    };
    for v in [json!(0.0), json!(-0.0), json!(1.0), json!(0.5)] {
        assert!(hgt(v.clone()).is_ok(), "hgt_p {v} refused");
    }
    for v in [json!(1.01), json!(-0.01), json!(true)] {
        assert!(hgt(v.clone()).is_err(), "hgt_p {v} accepted");
    }
    let plastic = |p: Value, diet: Value| {
        let mut s = set_save("plasticity");
        s["cells"][0][11] = p;
        s["cells"][0][12] = diet;
        load(&s)
    };
    let genetic = set_save("plasticity")["cells"][0][12].clone();
    assert!(plastic(json!(0.5), json!([0.2, 0.3, 0.5])).is_ok());
    // accepted by Python's sum, refused by plain `+` (review case)
    let near = json!([0.5695322860023156, 0.15395422311071535, 0.276514490886969]);
    assert!(plastic(json!(0.5), near).is_ok());
    // neutral arm: plast_p > 0, but its diet can never have moved
    let mut s = set_save("plastic_neutral");
    s["cells"][0][11] = json!(0.5);
    s["cells"][0][12] = json!([0.2, 0.3, 0.5]);
    let e = load(&s).expect_err("moved diet in the neutral arm accepted");
    assert!(
        e.message().contains("could not have moved"),
        "{}",
        e.message()
    );
    for (p, diet, why) in [
        (json!(1.01), genetic.clone(), "plast_p"),
        (json!(-0.01), genetic.clone(), "plast_p"),
        (json!(0.5), json!([0.2, 0.3, 0.6]), "diet"),
        (json!(0.5), json!([-0.1, 0.5, 0.6]), "diet"),
        (json!(0.5), json!([0.5, 0.5]), "diet"),
        (json!(0.0), json!([0.2, 0.3, 0.5]), "could not have moved"),
        // within 1e-6 of 1 for CPython 3.12's compensated sum, not for plain left-to-right `+`
        (
            json!(0.5),
            json!([0.20299530701092813, 0.3695882399078084, 0.42741545308126344]),
            "diet",
        ),
    ] {
        match plastic(p.clone(), diet.clone()) {
            Ok(_) => panic!("plast_p {p}, diet {diet} accepted"),
            Err(e) => assert!(e.message().contains(why), "{why}: {}", e.message()),
        }
    }
    let sexual = |v: Value| {
        let mut s = set_save("sex");
        s["cells"][0][10] = v;
        load(&s)
    };
    for v in [json!(0.0), json!(-0.0), json!(1.0), json!(0.5)] {
        assert!(sexual(v.clone()).is_ok(), "sex_p {v} refused");
    }
    for v in [json!(1.01), json!(-0.01), json!(true)] {
        assert!(sexual(v.clone()).is_err(), "sex_p {v} accepted");
    }
    // Python accepts a non-zero `defended` counter whatever the flag (it only reports it).
    let mut s = base_save();
    s["counters"]["defended"] = json!(7);
    assert!(load(&s).is_ok());
}

#[test]
fn ignored_parts_are_skipped() {
    // Unknown top-level keys and extra counters are skipped, as in Python; the tracker is
    // observer state the kernel never reads.
    let save = with(|s| {
        s["future_key"] = json!({"a": [1, 2, 3]});
        s["counters"]["hgt_events"] = json!(0);
        s["tracker"] = json!({"anything": [1, {"x": null}]});
    });
    let world = load(&save).expect("save with ignored parts");
    assert_eq!(state_hash(&world), hashes("default")[0].2);
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
    assert!(load_world(golden_dir("default").join("no_such_file.json.gz")).is_err());
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
