//! ADR-0016 (G3 P4): the read-only views equal `worldsim/views.py`. `views.json` in the golden root
//! (`scripts/g3_view_vectors.py`, regenerated on Linux by CI) holds, per set, at its start save and
//! after more steps: the SHA-256 of the tile words, the light factor, the state hash and some cell
//! records. The views go through the C ABI, as a front-end calls them, and must leave the state hash
//! unchanged.

mod common;

use common::{golden_dir, golden_root};
use serde_json::Value;
use sha2::{Digest, Sha256};
use worldsim_core::ffi::{
    ws_world_cell, ws_world_free, ws_world_info, ws_world_load, ws_world_state_hash, ws_world_step,
    ws_world_tiles, WsCell, WsInfo, WsWorld, WS_ERR_ARGUMENT, WS_ERR_INVALID, WS_HASH_LEN, WS_OK,
};

fn vectors() -> Value {
    let path = golden_root().join("views.json");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).expect("views.json")
}

fn f64_of(hex: &Value) -> f64 {
    let bytes: Vec<u8> = (0..8)
        .map(|i| u8::from_str_radix(&hex.as_str().unwrap()[2 * i..2 * i + 2], 16).unwrap())
        .collect();
    f64::from_le_bytes(bytes.try_into().unwrap())
}

fn f64s_of(list: &Value) -> Vec<u64> {
    list.as_array()
        .unwrap()
        .iter()
        .map(|v| f64_of(v).to_bits())
        .collect()
}

fn open(set: &str) -> *mut WsWorld {
    let data = std::fs::read(golden_dir(set).join("start.json.gz")).expect("start save");
    let h = unsafe { ws_world_load(data.as_ptr(), data.len()) };
    assert!(!h.is_null(), "{set}: load failed");
    h
}

fn hash(h: *mut WsWorld) -> String {
    let mut out = [0u8; WS_HASH_LEN];
    assert_eq!(
        unsafe { ws_world_state_hash(h, out.as_mut_ptr(), WS_HASH_LEN) },
        WS_OK
    );
    String::from_utf8(out.to_vec()).unwrap()
}

fn info(h: *mut WsWorld) -> WsInfo {
    let mut info = WsInfo::default();
    assert_eq!(unsafe { ws_world_info(h, &mut info) }, WS_OK);
    info
}

fn check(set: &str, h: *mut WsWorld, snap: &Value) {
    let i = info(h);
    let at = format!("{set} at step {}", snap["step"]);
    assert_eq!(i.step_count, snap["step"].as_u64().unwrap(), "{at}");
    let before = hash(h);
    assert_eq!(
        before,
        snap["state_hash"].as_str().unwrap(),
        "{at}: state hash"
    );
    assert_eq!(
        i.light_factor.to_bits(),
        f64_of(&snap["light_factor"]).to_bits(),
        "{at}: light factor"
    );
    let mut tiles = vec![0u8; i.width as usize * i.height as usize * 4];
    assert_eq!(
        unsafe { ws_world_tiles(h, tiles.as_mut_ptr(), tiles.len()) },
        WS_OK
    );
    let digest: String = Sha256::digest(&tiles)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect();
    assert_eq!(
        digest,
        snap["tiles_sha256"].as_str().unwrap(),
        "{at}: tiles"
    );
    for c in snap["cells"].as_array().unwrap() {
        let (x, y) = (
            c["x"].as_u64().unwrap() as u32,
            c["y"].as_u64().unwrap() as u32,
        );
        let mut r = WsCell::default();
        assert_eq!(unsafe { ws_world_cell(h, x, y, &mut r) }, WS_OK);
        let what = format!("{at}: cell at ({x}, {y})");
        assert_eq!(r.present, 1, "{what}");
        for key in ["id", "lineage", "age"] {
            let got = match key {
                "id" => r.id,
                "lineage" => r.lineage,
                _ => r.age,
            };
            assert_eq!(got, c[key].as_u64().unwrap(), "{what}: {key}");
        }
        assert_eq!(
            r.bonds as u64,
            c["bonds"].as_u64().unwrap(),
            "{what}: bonds"
        );
        assert_eq!(
            r.colony as u64,
            c["colony"].as_u64().unwrap(),
            "{what}: colony"
        );
        assert_eq!(
            r.rules as u64,
            c["rules"].as_u64().unwrap(),
            "{what}: rules"
        );
        assert_eq!(
            r.energy.to_bits(),
            f64_of(&c["energy"]).to_bits(),
            "{what}: energy"
        );
        let bits = |v: &[f64]| v.iter().map(|f| f.to_bits()).collect::<Vec<_>>();
        assert_eq!(bits(&r.genes), f64s_of(&c["genes"]), "{what}: genes");
        assert_eq!(bits(&r.shares), f64s_of(&c["shares"]), "{what}: shares");
        assert_eq!(bits(&r.traits), f64s_of(&c["traits"]), "{what}: traits");
    }
    assert_eq!(hash(h), before, "{at}: the views changed the state");
}

#[test]
fn views_equal_python_and_change_nothing() {
    let doc = vectors();
    let steps = doc["steps"].as_u64().unwrap() as u32;
    let cases = doc["cases"].as_array().unwrap();
    assert_eq!(cases.len(), 4);
    for case in cases {
        let set = case["set"].as_str().unwrap();
        let snaps = case["snapshots"].as_array().unwrap();
        let h = open(set);
        check(set, h, &snaps[0]);
        // views between every step must not disturb the stepping either
        for _ in 0..steps {
            assert_eq!(unsafe { ws_world_step(h, 1) }, WS_OK);
            let i = info(h);
            let mut tiles = vec![0u8; i.width as usize * i.height as usize * 4];
            assert_eq!(
                unsafe { ws_world_tiles(h, tiles.as_mut_ptr(), tiles.len()) },
                WS_OK
            );
        }
        check(set, h, &snaps[1]);
        unsafe { ws_world_free(h) };
    }
}

#[test]
fn an_empty_tile_is_absent_and_a_tile_outside_is_refused() {
    let h = open("default");
    let i = info(h);
    let mut tiles = vec![0u8; i.width as usize * i.height as usize * 4];
    assert_eq!(
        unsafe { ws_world_tiles(h, tiles.as_mut_ptr(), tiles.len()) },
        WS_OK
    );
    let empty = tiles
        .as_chunks::<4>()
        .0
        .iter()
        .position(|w| w[0] & 0x7 == 0)
        .expect("an empty tile");
    let (x, y) = (
        (empty % i.width as usize) as u32,
        (empty / i.width as usize) as u32,
    );
    let mut r = WsCell {
        present: 9,
        ..WsCell::default()
    };
    assert_eq!(unsafe { ws_world_cell(h, x, y, &mut r) }, WS_OK);
    assert_eq!(
        r,
        WsCell::default(),
        "an empty tile gives an all-zero record"
    );
    let mut untouched = WsCell {
        id: 7,
        ..WsCell::default()
    };
    for (x, y) in [(i.width, 0), (0, i.height), (u32::MAX, u32::MAX)] {
        assert_eq!(
            unsafe { ws_world_cell(h, x, y, &mut untouched) },
            WS_ERR_INVALID
        );
        assert_eq!(untouched.id, 7, "a refused call leaves *out untouched");
    }
    assert_eq!(
        unsafe { ws_world_step(h, 1) },
        WS_OK,
        "a refusal does not poison the handle"
    );
    let short = tiles.len() - 1;
    assert_eq!(
        unsafe { ws_world_tiles(h, tiles.as_mut_ptr(), short) },
        WS_ERR_ARGUMENT
    );
    assert_eq!(
        unsafe { ws_world_tiles(h, std::ptr::null_mut(), tiles.len()) },
        WS_ERR_ARGUMENT
    );
    assert_eq!(
        unsafe { ws_world_cell(h, 0, 0, std::ptr::null_mut()) },
        WS_ERR_ARGUMENT
    );
    unsafe { ws_world_free(h) };
}
