//! M4: the C ABI reproduces the golden hashes and refuses bad input without crashing.

mod common;

use common::{golden_dir, hashes, GOLDEN_SETS};
use worldsim_core::ffi::*;

fn last_error() -> String {
    unsafe {
        let n = ws_last_error(std::ptr::null_mut(), 0);
        let mut buf = vec![0u8; n];
        assert_eq!(ws_last_error(buf.as_mut_ptr(), n), n);
        String::from_utf8(buf).expect("utf-8 error")
    }
}

fn load_bytes(bytes: &[u8]) -> *mut WsWorld {
    unsafe { ws_world_load(bytes.as_ptr(), bytes.len()) }
}

fn hash_of(h: *mut WsWorld) -> String {
    let mut buf = [0u8; WS_HASH_LEN];
    assert_eq!(
        unsafe { ws_world_state_hash(h, buf.as_mut_ptr(), buf.len()) },
        WS_OK
    );
    String::from_utf8(buf.to_vec()).expect("hex")
}

fn golden_bytes(set: &str) -> Vec<u8> {
    std::fs::read(golden_dir(set).join("start.json.gz")).expect("golden save")
}

#[test]
fn golden_hashes_through_the_abi() {
    assert_eq!(ws_abi_version(), WS_ABI_VERSION);
    for set in GOLDEN_SETS {
        let rows = hashes(set);
        let h = load_bytes(&golden_bytes(set));
        assert!(!h.is_null(), "{set}: {}", last_error());
        assert_eq!(hash_of(h), rows[0].2, "{set}: start");
        // in uneven chunks, as a front-end at a variable speed would call it
        let (mut done, mut chunk) = (0usize, 1u32);
        while done + 1 < rows.len() {
            let n = chunk.min((rows.len() - 1 - done) as u32);
            assert_eq!(unsafe { ws_world_step(h, n) }, WS_OK);
            done += n as usize;
            assert_eq!(hash_of(h), rows[done].2, "{set}: step {}", rows[done].0);
            chunk = chunk % 37 + 7;
        }
        let mut info = WsInfo::default();
        assert_eq!(unsafe { ws_world_info(h, &mut info) }, WS_OK);
        let last = rows.last().unwrap();
        assert_eq!(
            (info.step_count, info.population),
            (last.0, last.1),
            "{set}: info"
        );
        let mut rgb = vec![0u8; info.width as usize * info.height as usize * 3];
        assert_eq!(
            unsafe { ws_world_render_rgb(h, rgb.as_mut_ptr(), rgb.len()) },
            WS_OK
        );
        assert!(rgb.iter().any(|&b| b != 0));
        unsafe { ws_world_free(h) };
    }
}

#[test]
fn bad_saves_return_null_with_a_message() {
    assert!(unsafe { ws_world_load(std::ptr::null(), 10) }.is_null());
    assert!(last_error().contains("empty"));
    assert!(load_bytes(b"not a gzip file").is_null());
    assert!(
        last_error().contains("not a valid save"),
        "{}",
        last_error()
    );
    let plain = br#"{"format": "worldsim-save", "version": 1}"#;
    let mut gz = Vec::new();
    {
        use std::io::Write;
        let mut e = flate2::write::GzEncoder::new(&mut gz, flate2::Compression::fast());
        e.write_all(plain).unwrap();
        e.finish().unwrap();
    }
    assert!(load_bytes(&gz).is_null());
    assert!(!last_error().is_empty());
}

#[test]
fn null_handles_and_wrong_buffers_are_refused() {
    let mut info = WsInfo::default();
    let mut hash = [0u8; WS_HASH_LEN];
    unsafe {
        assert_eq!(ws_world_step(std::ptr::null_mut(), 1), WS_ERR_ARGUMENT);
        assert_eq!(
            ws_world_info(std::ptr::null_mut(), &mut info),
            WS_ERR_ARGUMENT
        );
        assert_eq!(
            ws_world_state_hash(std::ptr::null_mut(), hash.as_mut_ptr(), WS_HASH_LEN),
            WS_ERR_ARGUMENT
        );
        ws_world_free(std::ptr::null_mut()); // ignored
    }
    let h = load_bytes(&golden_bytes("default"));
    assert!(!h.is_null());
    unsafe {
        assert_eq!(ws_world_info(h, std::ptr::null_mut()), WS_ERR_ARGUMENT);
        assert_eq!(
            ws_world_state_hash(h, hash.as_mut_ptr(), WS_HASH_LEN - 1),
            WS_ERR_ARGUMENT
        );
        assert_eq!(ws_world_info(h, &mut info), WS_OK);
        let mut short = vec![0u8; info.width as usize * info.height as usize * 3 - 1];
        assert_eq!(
            ws_world_render_rgb(h, short.as_mut_ptr(), short.len()),
            WS_ERR_ARGUMENT
        );
        assert!(last_error().contains("render buffer"));
        assert_eq!(
            ws_world_render_rgb(h, std::ptr::null_mut(), 0),
            WS_ERR_ARGUMENT
        );
        // the handle is still usable after refused calls
        assert_eq!(ws_world_step(h, 1), WS_OK);
        ws_world_free(h);
    }
}

#[test]
fn a_refused_save_reports_its_reason() {
    use std::io::{Read, Write};
    let mut json = String::new();
    flate2::read::GzDecoder::new(&golden_bytes("default")[..])
        .read_to_string(&mut json)
        .unwrap();
    let json = json.replacen("\"sensing\":false", "\"sensing\":1", 1);
    let mut gz = Vec::new();
    let mut e = flate2::write::GzEncoder::new(&mut gz, flate2::Compression::fast());
    e.write_all(json.as_bytes()).unwrap();
    e.finish().unwrap();
    assert!(load_bytes(&gz).is_null());
    assert!(
        last_error().contains("sensing must be bool"),
        "{}",
        last_error()
    );
}

#[test]
fn a_hostile_save_cannot_make_a_huge_error_message() {
    use std::io::Write;
    let json = format!(
        r#"{{"format": "worldsim-save", "step_count": "{}"}}"#,
        "A".repeat(1_000_000)
    );
    let mut gz = Vec::new();
    let mut e = flate2::write::GzEncoder::new(&mut gz, flate2::Compression::best());
    e.write_all(json.as_bytes()).unwrap();
    e.finish().unwrap();
    assert!(load_bytes(&gz).is_null());
    let n = unsafe { ws_last_error(std::ptr::null_mut(), 0) };
    assert!(n <= worldsim_core::MAX_MESSAGE + 3, "message of {n} bytes");
    assert!(last_error().ends_with("..."));
}

#[test]
fn last_error_truncates_to_the_buffer() {
    assert!(load_bytes(b"x").is_null());
    let full = last_error();
    let mut small = [0u8; 4];
    let n = unsafe { ws_last_error(small.as_mut_ptr(), small.len()) };
    assert_eq!(n, full.len());
    assert_eq!(&small, &full.as_bytes()[..4]);
}

// ------------------------------------------------------------------ ws_world_create (ADR-0012)

fn create(config: &[u8], seed: u64) -> *mut WsWorld {
    unsafe { ws_world_create(config.as_ptr(), config.len(), seed) }
}

fn creation_config(set: &str) -> String {
    std::fs::read_to_string(golden_dir(set).join("config.json")).expect("config.json")
}

fn creation_seed(set: &str) -> u64 {
    let text = std::fs::read_to_string(golden_dir(set).join("rng.json")).expect("rng.json");
    let v: serde_json::Value = serde_json::from_str(&text).expect("json");
    v["seed"].as_u64().expect("seed")
}

/// `ws_world_create` with `config` edited as a JSON object, expecting null and `reason` in the error.
fn refused(edit: impl FnOnce(&mut serde_json::Map<String, serde_json::Value>), reason: &str) {
    let mut v: serde_json::Value =
        serde_json::from_str(&creation_config("create_default")).unwrap();
    edit(v.as_object_mut().unwrap());
    let h = create(v.to_string().as_bytes(), 1);
    assert!(h.is_null(), "accepted, expected: {reason}");
    assert!(
        last_error().contains(reason),
        "{} (expected {reason})",
        last_error()
    );
}

#[test]
fn created_worlds_follow_the_creation_sets() {
    for set in common::CREATE_SETS {
        let rows = hashes(set);
        let h = create(creation_config(set).as_bytes(), creation_seed(set));
        assert!(!h.is_null(), "{set}: {}", last_error());
        assert_eq!(hash_of(h), rows[0].2, "{set}: step 0");
        let (mut done, mut chunk) = (0usize, 1u32);
        while done + 1 < rows.len() {
            let n = chunk.min((rows.len() - 1 - done) as u32);
            assert_eq!(unsafe { ws_world_step(h, n) }, WS_OK);
            done += n as usize;
            assert_eq!(hash_of(h), rows[done].2, "{set}: step {}", rows[done].0);
            chunk = chunk % 37 + 7;
        }
        unsafe { ws_world_free(h) };
    }
}

#[test]
fn the_handle_of_a_created_world_equals_world_new() {
    let config = creation_config("create_volcanic");
    for seed in [0, 7, u64::MAX] {
        let h = create(config.as_bytes(), seed);
        assert!(!h.is_null(), "{}", last_error());
        let cfg = worldsim_core::save::config_from_json(config.as_bytes()).unwrap();
        let world = worldsim_core::world::World::new(cfg, seed);
        assert_eq!(
            hash_of(h),
            worldsim_core::hash::state_hash(&world),
            "seed {seed}"
        );
        unsafe { ws_world_free(h) };
    }
}

#[test]
fn bad_configs_return_null_with_a_message() {
    assert!(unsafe { ws_world_create(std::ptr::null(), 10, 1) }.is_null());
    assert!(last_error().contains("empty config"));
    assert!(create(b"", 1).is_null());
    assert!(last_error().contains("empty config"));
    let huge = vec![b' '; WS_MAX_CONFIG_LEN + 1];
    assert!(create(&huge, 1).is_null());
    assert!(last_error().contains("larger than"), "{}", last_error());
    for (text, reason) in [
        (&b"not json"[..], "invalid config"),
        (b"[1, 2]", "invalid config"),
        (b"{\"width\": {\"nested\": 1}}", "invalid config"),
        (b"\xff\xfe", "invalid config"),
    ] {
        assert!(create(text, 1).is_null());
        assert!(last_error().contains(reason), "{}", last_error());
    }
    refused(
        |m| drop(m.insert("no_such_field".into(), 1.into())),
        "unknown key",
    );
    refused(|m| drop(m.remove("vent_count")), "vent_count");
    refused(|m| drop(m.insert("width".into(), 0.into())), "width");
    refused(
        |m| drop(m.insert("rock_fraction".into(), 0.95.into())),
        "rock_fraction",
    );
    refused(
        |m| drop(m.insert("vent_strength".into(), 1.0e7.into())),
        "vent_strength",
    );
    refused(
        |m| drop(m.insert("sex".into(), 1.into())),
        "sex must be bool",
    );
    refused(
        |m| {
            m.insert("width".into(), 10_000.into());
            m.insert("height".into(), 10_000.into());
        },
        "exceeds",
    );
    // a duplicate key, which serde_json::Value cannot hold: edit the text
    let config = creation_config("create_default");
    let dup = config.replacen("{", "{\"width\":160,", 1);
    assert!(create(dup.as_bytes(), 1).is_null());
    assert!(
        last_error().contains("duplicate config key"),
        "{}",
        last_error()
    );
}

// ------------------------------------------------------------------ interventions (ADR-0013)

fn intervene(h: *mut WsWorld, kind: u32, x: u32, y: u32, radius: u32, amount: f64) -> (i32, u64) {
    let mut changed = u64::MAX; // a refusal must leave it untouched
    let code = unsafe { ws_world_intervene(h, kind, x, y, radius, amount, &mut changed) };
    (code, changed)
}

fn render_of(h: *mut WsWorld) -> Vec<u8> {
    let mut info = WsInfo::default();
    assert_eq!(unsafe { ws_world_info(h, &mut info) }, WS_OK);
    let mut rgb = vec![0u8; info.width as usize * info.height as usize * 3];
    assert_eq!(
        unsafe { ws_world_render_rgb(h, rgb.as_mut_ptr(), rgb.len()) },
        WS_OK
    );
    rgb
}

fn interventions_vectors() -> serde_json::Value {
    let path = common::golden_root().join("interventions.json");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).expect("interventions.json")
}

#[test]
fn interventions_through_the_abi_follow_the_vectors() {
    let v = interventions_vectors();
    for case in v["cases"].as_array().unwrap() {
        let name = case["name"].as_str().unwrap();
        let h = load_bytes(&golden_bytes(case["set"].as_str().unwrap()));
        assert!(!h.is_null(), "{name}: {}", last_error());
        let hashes = case["hashes"].as_array().unwrap();
        let mut info = WsInfo::default();
        let mut row = 0;
        for a in case["actions"].as_array().unwrap() {
            let step = a["step"].as_u64().unwrap();
            assert_eq!(unsafe { ws_world_info(h, &mut info) }, WS_OK);
            if step > info.step_count {
                assert_eq!(
                    unsafe { ws_world_step(h, (step - info.step_count) as u32) },
                    WS_OK
                );
                row += (step - info.step_count) as usize;
                assert_eq!(
                    hash_of(h),
                    hashes[row][2].as_str().unwrap(),
                    "{name}: step {step}"
                );
            }
            let u = |k: &str| a[k].as_u64().unwrap() as u32;
            let (code, changed) = intervene(
                h,
                u("kind"),
                u("x"),
                u("y"),
                u("radius"),
                a["amount"].as_f64().unwrap(),
            );
            assert_eq!(code, WS_OK, "{name} at step {step}: {}", last_error());
            assert_eq!(changed, a["ret"].as_u64().unwrap(), "{name} at step {step}");
            assert_eq!(
                hash_of(h),
                a["hash"].as_str().unwrap(),
                "{name} at step {step}"
            );
        }
        let rest = (hashes.len() - 1 - row) as u32;
        assert_eq!(unsafe { ws_world_step(h, rest) }, WS_OK);
        assert_eq!(
            hash_of(h),
            hashes.last().unwrap()[2].as_str().unwrap(),
            "{name}: end"
        );
        unsafe { ws_world_free(h) };
    }
}

#[test]
fn the_handle_of_an_edited_world_equals_world_intervene() {
    use worldsim_core::world::Intervention;
    let bytes = golden_bytes("volcanic");
    let h = load_bytes(&bytes);
    let mut world =
        worldsim_core::save::world_from_gzip(&bytes, worldsim_core::save::MAX_SAVE_BYTES).unwrap();
    let edits = [
        (WS_EDIT_NUTRIENTS, 10, 5, 4, 15.0),
        (WS_EDIT_METEORITE, 70, 30, 6, 0.0),
        (WS_EDIT_RAISE_ROCK, 20, 2, 3, 0.0),
        (WS_EDIT_VENT, 120, 30, 0, 4.0),
        (WS_EDIT_DIG, 20, 2, 5, 0.0),
    ];
    for (kind, x, y, radius, amount) in edits {
        let (code, changed) = intervene(h, kind, x, y, radius, amount);
        assert_eq!(code, WS_OK, "{}", last_error());
        let want = world
            .intervene(Intervention::from_raw(kind, x, y, radius, amount).unwrap())
            .unwrap();
        assert_eq!(changed, want, "kind {kind}");
        assert_eq!(
            hash_of(h),
            worldsim_core::hash::state_hash(&world),
            "kind {kind}"
        );
        assert_eq!(unsafe { ws_world_step(h, 3) }, WS_OK);
        for _ in 0..3 {
            world.step();
        }
    }
    assert_eq!(hash_of(h), worldsim_core::hash::state_hash(&world));
    unsafe { ws_world_free(h) };
}

#[test]
fn refused_edits_change_nothing_and_keep_the_handle_usable() {
    let bytes = golden_bytes("default");
    let h = load_bytes(&bytes);
    let mut info = WsInfo::default();
    assert_eq!(unsafe { ws_world_info(h, &mut info) }, WS_OK);
    let (w, hh) = (info.width, info.height);
    let mut changed = 0u64;
    // null handle and null out pointer are argument errors
    assert_eq!(
        unsafe {
            ws_world_intervene(
                std::ptr::null_mut(),
                WS_EDIT_DIG,
                0,
                0,
                1,
                0.0,
                &mut changed,
            )
        },
        WS_ERR_ARGUMENT
    );
    assert!(last_error().contains("null world handle"));
    assert_eq!(
        unsafe { ws_world_intervene(h, WS_EDIT_DIG, 0, 0, 1, 0.0, std::ptr::null_mut()) },
        WS_ERR_ARGUMENT
    );
    assert!(last_error().contains("out_changed"));
    // a big nutrient pile on one tile, so a second one passes the cap
    assert_eq!(intervene(h, WS_EDIT_NUTRIENTS, 5, 5, 0, 5e11), (WS_OK, 1));
    let before = (hash_of(h), render_of(h));
    let bad: [(u32, u32, u32, u32, f64, &str); 17] = [
        (0, 1, 1, 1, 0.0, "unknown intervention kind 0"),
        (6, 1, 1, 1, 0.0, "unknown intervention kind 6"),
        (WS_EDIT_METEORITE, w, 0, 1, 0.0, "outside"),
        (WS_EDIT_DIG, 0, hh, 1, 0.0, "outside"),
        (WS_EDIT_VENT, u32::MAX, 0, 0, 4.0, "outside"),
        (WS_EDIT_METEORITE, 1, 1, 1, 1.0, "amount must be 0"),
        (WS_EDIT_RAISE_ROCK, 1, 1, 1, -0.0, "amount must be 0"),
        (WS_EDIT_DIG, 1, 1, 1, f64::NAN, "amount must be 0"),
        (WS_EDIT_VENT, 1, 1, 1, 4.0, "radius must be 0"),
        (WS_EDIT_NUTRIENTS, 1, 1, 1, f64::NAN, "finite"),
        (WS_EDIT_NUTRIENTS, 1, 1, 1, f64::INFINITY, "finite"),
        (WS_EDIT_NUTRIENTS, 1, 1, 1, -1.0, ">= 0"),
        (WS_EDIT_NUTRIENTS, 1, 1, 1, -0.0, ">= 0"),
        (WS_EDIT_VENT, 1, 1, 0, f64::NAN, "max_chem"),
        (WS_EDIT_VENT, 1, 1, 0, -2.0, "max_chem"),
        (WS_EDIT_NUTRIENTS, 5, 5, 2, 6e11, "above"),
        (WS_EDIT_NUTRIENTS, 30, 30, 2, f64::MAX, "above"),
    ];
    for (kind, x, y, radius, amount, msg) in bad {
        let (code, changed) = intervene(h, kind, x, y, radius, amount);
        assert_eq!(
            code, WS_ERR_INVALID,
            "{kind} ({x}, {y}) r {radius} a {amount}"
        );
        assert!(last_error().contains(msg), "{}", last_error());
        assert_eq!(changed, u64::MAX, "out_changed written on refusal");
        // the state hash covers organic and cells, the render rock, chem and light
        assert_eq!(
            (hash_of(h), render_of(h)),
            before,
            "{kind}: refused but changed"
        );
    }
    // still usable: steps like a handle that never saw the refusals
    let twin = load_bytes(&bytes);
    assert_eq!(
        intervene(twin, WS_EDIT_NUTRIENTS, 5, 5, 0, 5e11),
        (WS_OK, 1)
    );
    assert_eq!(unsafe { ws_world_step(h, 5) }, WS_OK);
    assert_eq!(unsafe { ws_world_step(twin, 5) }, WS_OK);
    assert_eq!(hash_of(h), hash_of(twin));
    unsafe {
        ws_world_free(h);
        ws_world_free(twin);
    }
}
