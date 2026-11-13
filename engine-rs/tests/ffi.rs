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
        |m| drop(m.insert("sense_range".into(), true.into())),
        "sense_range is not supported",
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

// ------------------------------------------------------------------ the game (ADR-0017, ABI 5)

fn games_vectors() -> serde_json::Value {
    let path = common::golden_root().join("games.json");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).expect("games.json")
}

fn game_info(h: *mut WsWorld) -> WsGameInfo {
    let mut info = WsGameInfo::default();
    assert_eq!(
        unsafe { ws_game_info(h, &mut info) },
        WS_OK,
        "{}",
        last_error()
    );
    info
}

fn act(h: *mut WsWorld, tool: u32, x: u32, y: u32) -> (i32, u32) {
    let mut accepted = u32::MAX; // an error must leave it untouched
    let code = unsafe { ws_game_act(h, tool, x, y, &mut accepted) };
    (code, accepted)
}

fn f64_hex(v: f64) -> String {
    v.to_le_bytes().iter().map(|b| format!("{b:02x}")).collect()
}

fn tool_code(name: &str) -> u32 {
    let i = worldsim_core::game::Tool::ALL
        .iter()
        .position(|t| t.name() == name)
        .expect("tool name");
    i as u32 + 1
}

#[test]
fn default_rules_through_the_abi_equal_python() {
    let v = games_vectors();
    let mut rules = WsGameRules {
        reserved: 7,
        ..WsGameRules::default()
    };
    assert_eq!(unsafe { ws_game_default_rules(&mut rules) }, WS_OK);
    let python = WsGameRules::from(&common::game_rules_of(&v["default_rules"]));
    assert_eq!(rules, python);
    assert_eq!(rules.reserved, 0);
    assert_eq!(
        unsafe { ws_game_default_rules(std::ptr::null_mut()) },
        WS_ERR_ARGUMENT
    );
}

#[test]
fn games_through_the_abi_follow_the_vectors() {
    let v = games_vectors();
    for case in v["cases"].as_array().unwrap() {
        let name = case["name"].as_str().unwrap();
        let h = load_bytes(&golden_bytes(case["set"].as_str().unwrap()));
        let rules = WsGameRules::from(&common::game_rules_of(&case["rules"]));
        assert_eq!(
            unsafe { ws_game_attach(h, &rules) },
            WS_OK,
            "{name}: {}",
            last_error()
        );
        let start = case["start_step"].as_u64().unwrap();
        let steps = case["steps"].as_u64().unwrap();
        let actions = case["actions"].as_array().unwrap();
        let hashes: std::collections::HashMap<u64, String> = case["hashes"]
            .as_array()
            .unwrap()
            .iter()
            .map(|r| (r[0].as_u64().unwrap(), r[1].as_str().unwrap().to_string()))
            .collect();
        // step in chunks that stop at every action offset and every recorded hash
        let mut stops: Vec<u64> = actions
            .iter()
            .map(|a| a["offset"].as_u64().unwrap())
            .chain(hashes.keys().map(|s| s - start))
            .collect();
        stops.sort_unstable();
        stops.dedup();
        let (mut k, mut next_action) = (0u64, 0usize);
        for stop in stops {
            assert_eq!(unsafe { ws_world_step(h, (stop - k) as u32) }, WS_OK);
            k = stop;
            while next_action < actions.len()
                && actions[next_action]["offset"].as_u64().unwrap() <= k
            {
                let a = &actions[next_action];
                let (code, accepted) = act(
                    h,
                    tool_code(a["tool"].as_str().unwrap()),
                    a["x"].as_u64().unwrap() as u32,
                    a["y"].as_u64().unwrap() as u32,
                );
                assert_eq!(code, WS_OK, "{name}: {a}: {}", last_error());
                assert_eq!(
                    (accepted == 1, f64_hex(game_info(h).budget)),
                    (
                        a["accepted"].as_bool().unwrap(),
                        a["budget"].as_str().unwrap().to_string()
                    ),
                    "{name}: {a}"
                );
                next_action += 1;
            }
            if let Some(want) = hashes.get(&(start + k)) {
                assert_eq!(&hash_of(h), want, "{name}: hash at offset {k}");
            }
        }
        assert_eq!(k, steps, "{name}: the last hash is at the last step");
        assert_eq!(next_action, actions.len());
        let info = game_info(h);
        assert_eq!(
            f64_hex(info.budget),
            case["budget"].as_str().unwrap(),
            "{name}"
        );
        assert_eq!(
            info.player_vents,
            case["player_vents"].as_u64().unwrap(),
            "{name}"
        );
        for (i, m) in worldsim_core::game::Milestone::ALL.iter().enumerate() {
            let want = case["achieved"][m.name()].as_u64();
            assert_eq!(
                info.reached & (1 << i) != 0,
                want.is_some(),
                "{name}: {}",
                m.name()
            );
            assert_eq!(
                info.reached_step[i],
                want.unwrap_or(0),
                "{name}: {}",
                m.name()
            );
        }
        unsafe { ws_world_free(h) };
    }
}

#[test]
fn game_calls_refuse_bad_input_and_change_nothing() {
    let h = load_bytes(&golden_bytes("default"));
    let mut info = WsGameInfo::default();
    // no game yet: the game calls are refused
    assert_eq!(unsafe { ws_game_info(h, &mut info) }, WS_ERR_INVALID);
    assert!(last_error().contains("no game"));
    assert_eq!(act(h, WS_TOOL_METEORITE, 1, 1), (WS_ERR_INVALID, u32::MAX));
    // null pointers
    let good = WsGameRules::from(&worldsim_core::game::GameRules::default());
    assert_eq!(
        unsafe { ws_game_attach(std::ptr::null_mut(), &good) },
        WS_ERR_ARGUMENT
    );
    assert_eq!(
        unsafe { ws_game_attach(h, std::ptr::null()) },
        WS_ERR_ARGUMENT
    );
    assert_eq!(
        unsafe { ws_game_info(h, std::ptr::null_mut()) },
        WS_ERR_ARGUMENT
    );
    assert_eq!(
        unsafe { ws_game_act(h, WS_TOOL_DIG, 1, 1, std::ptr::null_mut()) },
        WS_ERR_ARGUMENT
    );
    // rules out of bounds: refused, and the world still takes a good game afterwards
    let bad: [(WsGameRules, &str); 8] = [
        (
            WsGameRules {
                reserved: 1,
                ..good
            },
            "reserved",
        ),
        (
            WsGameRules {
                regen: f64::NAN,
                ..good
            },
            "regen",
        ),
        (
            WsGameRules {
                budget_max: f64::INFINITY,
                ..good
            },
            "budget_max",
        ),
        (
            WsGameRules {
                budget_start: -0.0,
                ..good
            },
            "budget_start",
        ),
        (
            WsGameRules {
                kill_fraction: 1e13,
                ..good
            },
            "kill_fraction",
        ),
        (
            WsGameRules {
                cost: [10.0, 20.0, -4.0, 4.0, 40.0],
                ..good
            },
            "cost[mountain]",
        ),
        (
            WsGameRules {
                radius: [6, 10, 2, 2, u32::MAX],
                ..good
            },
            "radius[volcano]",
        ),
        (
            WsGameRules {
                check_every: 0,
                ..good
            },
            "check_every",
        ),
    ];
    let before = hash_of(h);
    for (rules, msg) in bad {
        assert_eq!(
            unsafe { ws_game_attach(h, &rules) },
            WS_ERR_INVALID,
            "{msg}"
        );
        assert!(last_error().contains(msg), "{}", last_error());
        assert_eq!(
            unsafe { ws_game_info(h, &mut info) },
            WS_ERR_INVALID,
            "{msg}: attached"
        );
    }
    assert_eq!(hash_of(h), before);
    assert_eq!(unsafe { ws_game_attach(h, &good) }, WS_OK);
    // a second game is refused; plain edits are refused while a game is attached
    assert_eq!(unsafe { ws_game_attach(h, &good) }, WS_ERR_INVALID);
    assert!(last_error().contains("already has a game"));
    assert_eq!(
        intervene(h, WS_EDIT_NUTRIENTS, 5, 5, 1, 1.0),
        (WS_ERR_INVALID, u64::MAX)
    );
    assert!(last_error().contains("ws_game_act"));
    assert_eq!(hash_of(h), before);
    // unknown tools are errors; off-world actions are free refusals
    for tool in [0, 6, u32::MAX] {
        assert_eq!(
            act(h, tool, 1, 1),
            (WS_ERR_INVALID, u32::MAX),
            "tool {tool}"
        );
        assert!(last_error().contains("unknown tool"));
    }
    assert_eq!(act(h, WS_TOOL_METEORITE, u32::MAX, 0), (WS_OK, 0));
    assert_eq!(game_info(h).budget, 100.0);
    assert_eq!(hash_of(h), before);
    // a kernel refusal (organic above the cap) changes neither the world nor the game
    let rich = WsGameRules {
        nutrients_amount: 6e11,
        ..good
    };
    let h2 = load_bytes(&golden_bytes("default"));
    assert_eq!(unsafe { ws_game_attach(h2, &rich) }, WS_OK);
    assert_eq!(act(h2, WS_TOOL_NUTRIENTS, 10, 10), (WS_OK, 1));
    let (state, game) = (hash_of(h2), game_info(h2));
    assert_eq!(
        act(h2, WS_TOOL_NUTRIENTS, 10, 10),
        (WS_ERR_INVALID, u32::MAX)
    );
    assert!(last_error().contains("above"));
    assert_eq!((hash_of(h2), game_info(h2)), (state, game));
    // both still step
    assert_eq!(unsafe { ws_world_step(h, 3) }, WS_OK);
    assert_eq!(unsafe { ws_world_step(h2, 3) }, WS_OK);
    unsafe {
        ws_world_free(h);
        ws_world_free(h2);
    }
}

// ------------------------------------------------------------------ species (ABI 6, ADR-0018)

fn species_vectors() -> serde_json::Value {
    let path = common::golden_root().join("species.json");
    serde_json::from_str(&std::fs::read_to_string(&path).expect("species.json")).expect("json")
}

fn species_info(h: *mut WsWorld) -> WsSpeciesInfo {
    let mut info = WsSpeciesInfo::default();
    assert_eq!(unsafe { ws_world_species_info(h, &mut info) }, WS_OK);
    info
}

fn species_by_id(h: *mut WsWorld, id: u64) -> (i32, WsSpecies) {
    let mut s = WsSpecies::default();
    let code = unsafe { ws_world_species_by_id(h, id, &mut s) };
    (code, s)
}

/// A dump row (`Species.to_list()`) as the ABI lays it out.
fn ws_species_of(row: &serde_json::Value) -> WsSpecies {
    let r = row.as_array().unwrap();
    let step = |v: &serde_json::Value| v.as_u64().unwrap_or(WS_STEP_NONE);
    let origin = match r[2].as_str().unwrap() {
        "seed" => WS_ORIGIN_SEED,
        "immigrant" => WS_ORIGIN_IMMIGRANT,
        "speciation" => WS_ORIGIN_SPECIATION,
        other => panic!("origin {other}"),
    };
    WsSpecies {
        id: r[0].as_u64().unwrap(),
        parent: r[1].as_u64().unwrap_or(0),
        born: r[4].as_u64().unwrap(),
        extinct: step(&r[5]),
        count: r[6].as_u64().unwrap(),
        peak: r[7].as_u64().unwrap(),
        activity: r[8].as_u64().unwrap(),
        established: step(&r[9]),
        children: r[10].as_u64().unwrap(),
        origin,
        reserved: 0,
    }
}

/// Every cell's `[id, species]` read through `ws_world_cell`, in id order.
fn cells_through_the_abi(h: *mut WsWorld) -> Vec<(u64, u64)> {
    let mut info = WsInfo::default();
    assert_eq!(unsafe { ws_world_info(h, &mut info) }, WS_OK);
    let mut out = Vec::new();
    for y in 0..info.height {
        for x in 0..info.width {
            let mut c = WsCell::default();
            assert_eq!(unsafe { ws_world_cell(h, x, y, &mut c) }, WS_OK);
            if c.present == 1 {
                out.push((c.id, c.species));
            }
        }
    }
    out.sort_unstable();
    out
}

#[test]
fn species_through_the_abi_follow_the_vectors() {
    let doc = species_vectors();
    for name in ["created_default", "tracked_save"] {
        let case = doc["cases"]
            .as_array()
            .unwrap()
            .iter()
            .find(|c| c["name"] == name)
            .unwrap();
        let h = if case["config"].is_null() {
            let save = common::golden_root().join(case["save"].as_str().unwrap());
            load_bytes(&std::fs::read(save).expect("tracked save"))
        } else {
            let seed: u64 = case["seed"].as_str().unwrap().parse().unwrap();
            create(case["config"].to_string().as_bytes(), seed)
        };
        assert!(!h.is_null(), "{name}: {}", last_error());
        let (mut left, mut chunk) = (case["steps"].as_u64().unwrap() as u32, 1u32);
        while left > 0 {
            let n = chunk.min(left);
            assert_eq!(unsafe { ws_world_step(h, n) }, WS_OK);
            left -= n;
            chunk = chunk % 53 + 11;
        }
        let d = &case["tracker"];
        let rows = d["species"].as_array().unwrap();
        let extant: Vec<WsSpecies> = rows
            .iter()
            .map(ws_species_of)
            .filter(|s| s.extinct == WS_STEP_NONE)
            .collect();
        let want = WsSpeciesInfo {
            tracked: 1,
            reserved: 0,
            extant: extant.len() as u64,
            retained: rows.len() as u64,
            next_id: d["next_id"].as_u64().unwrap(),
            speciations: d["speciations"].as_u64().unwrap(),
            novelty: d["novelty"].as_u64().unwrap(),
            pruned: d["pruned"].as_u64().unwrap(),
        };
        assert_eq!(species_info(h), want, "{name}: species info");
        for (i, s) in extant.iter().enumerate() {
            let mut got = WsSpecies::default();
            assert_eq!(unsafe { ws_world_species(h, i as u64, &mut got) }, WS_OK);
            assert_eq!(&got, s, "{name}: living species {i}");
        }
        for row in rows {
            let s = ws_species_of(row);
            assert_eq!(
                species_by_id(h, s.id),
                (WS_OK, s),
                "{name}: species {}",
                s.id
            );
        }
        let cells: Vec<(u64, u64)> = case["cells"]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| (p[0].as_u64().unwrap(), p[1].as_u64().unwrap()))
            .collect();
        assert_eq!(cells_through_the_abi(h), cells, "{name}: cells' species");
        unsafe { ws_world_free(h) };
    }
}

#[test]
fn species_calls_refuse_bad_input_and_keep_the_handle_usable() {
    // an untracked save: no species, the views refused, the handle usable
    let h = load_bytes(&golden_bytes("default"));
    assert_eq!(species_info(h), WsSpeciesInfo::default());
    let mut s = WsSpecies {
        id: 7,
        ..WsSpecies::default()
    };
    assert_eq!(unsafe { ws_world_species(h, 0, &mut s) }, WS_ERR_INVALID);
    assert!(last_error().contains("does not track"));
    assert_eq!(
        unsafe { ws_world_species_by_id(h, 1, &mut s) },
        WS_ERR_INVALID
    );
    assert_eq!(s.id, 7, "a refused call leaves *out untouched");
    assert!(cells_through_the_abi(h).iter().all(|&(_, sp)| sp == 0));
    assert_eq!(unsafe { ws_world_step(h, 3) }, WS_OK);
    unsafe { ws_world_free(h) };

    // a tracked world: indexes and ids out of range are refused
    let h = create(
        creation_config("create_default").as_bytes(),
        creation_seed("create_default"),
    );
    assert_eq!(unsafe { ws_world_step(h, 50) }, WS_OK);
    let info = species_info(h);
    assert_eq!(info.tracked, 1);
    assert!(info.extant > 0);
    for index in [info.extant, u64::MAX] {
        assert_eq!(
            unsafe { ws_world_species(h, index, &mut s) },
            WS_ERR_INVALID
        );
        assert_eq!(s.id, 7);
    }
    assert!(last_error().contains("past the"));
    for id in [0, info.next_id + 1, u64::MAX] {
        assert_eq!(species_by_id(h, id).0, WS_ERR_INVALID, "id {id}");
    }
    let null_species: *mut WsSpecies = std::ptr::null_mut();
    assert_eq!(
        unsafe { ws_world_species_info(h, std::ptr::null_mut()) },
        WS_ERR_ARGUMENT
    );
    assert_eq!(
        unsafe { ws_world_species(h, 0, null_species) },
        WS_ERR_ARGUMENT
    );
    assert_eq!(
        unsafe { ws_world_species_by_id(h, 1, null_species) },
        WS_ERR_ARGUMENT
    );
    let mut i = WsSpeciesInfo::default();
    assert_eq!(
        unsafe { ws_world_species_info(std::ptr::null(), &mut i) },
        WS_ERR_ARGUMENT
    );
    // the ancestry walk ends at a root or at a pruned ancestor, through ever older species
    let mut last = WsSpecies::default();
    assert_eq!(
        unsafe { ws_world_species(h, info.extant - 1, &mut last) },
        WS_OK
    );
    let (mut id, mut child) = (last.parent, last.id);
    while id != 0 {
        let (code, p) = species_by_id(h, id);
        if code != WS_OK {
            break; // pruned ancestor
        }
        assert!(p.id < child);
        (id, child) = (p.parent, p.id);
    }
    assert_eq!(unsafe { ws_world_step(h, 1) }, WS_OK, "still usable");
    unsafe { ws_world_free(h) };
}

#[test]
fn a_tracked_world_keys_its_tiles_by_species() {
    let h = create(
        creation_config("create_default").as_bytes(),
        creation_seed("create_default"),
    );
    assert_eq!(unsafe { ws_world_step(h, 20) }, WS_OK);
    let mut info = WsInfo::default();
    assert_eq!(unsafe { ws_world_info(h, &mut info) }, WS_OK);
    let mut tiles = vec![0u8; info.width as usize * info.height as usize * 4];
    assert_eq!(
        unsafe { ws_world_tiles(h, tiles.as_mut_ptr(), tiles.len()) },
        WS_OK
    );
    let mut seen = 0;
    for (i, word) in tiles.as_chunks::<4>().0.iter().enumerate() {
        let word = u32::from_le_bytes(*word);
        let (x, y) = (
            (i % info.width as usize) as u32,
            (i / info.width as usize) as u32,
        );
        let mut c = WsCell::default();
        assert_eq!(unsafe { ws_world_cell(h, x, y, &mut c) }, WS_OK);
        if c.present == 1 {
            assert_ne!(c.species, 0);
            assert_eq!(u64::from(word >> 16), c.species % 65_536);
            seen += 1;
        }
    }
    assert!(seen > 0);
    unsafe { ws_world_free(h) };
}
