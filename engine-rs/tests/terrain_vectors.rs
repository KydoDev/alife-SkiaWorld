//! ADR-0012 piece 3 and ADR-0013 piece 1: `generate_terrain` and `vent_plume` equal Python's on every
//! case of `scripts/g2_terrain_vectors.py` (SHA-256 of each map). The file sits in the golden root, so CI
//! compares against copies regenerated on Linux (libm `sin`/`exp` are per platform).

mod common;

use serde_json::Value;
use sha2::{Digest, Sha256};
use std::time::Instant;
use worldsim_core::terrain::{generate_terrain, vent_plume, TerrainParams};

fn vectors() -> Value {
    let path = common::golden_root().join("terrain.json");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).expect("terrain.json")
}

fn digest_f64(values: &[f64]) -> String {
    let mut h = Sha256::new();
    for v in values {
        h.update(v.to_le_bytes());
    }
    hex(&h.finalize())
}

fn digest_bool(values: &[bool]) -> String {
    let bytes: Vec<u8> = values.iter().map(|&b| u8::from(b)).collect();
    hex(&Sha256::digest(&bytes))
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn params(p: &Value) -> TerrainParams {
    TerrainParams {
        width: p["width"].as_u64().unwrap() as usize,
        height: p["height"].as_u64().unwrap() as usize,
        organic_init: p["organic_init"].as_f64().unwrap(),
        rock_fraction: p["rock_fraction"].as_f64().unwrap(),
        vent_count: p["vent_count"].as_i64().unwrap(),
        vent_strength: p["vent_strength"].as_f64().unwrap(),
        vent_radius: p["vent_radius"].as_f64().unwrap(),
    }
}

#[test]
fn terrain_equals_python() {
    let v = vectors();
    let cases = v["terrain"].as_array().unwrap();
    assert!(cases.len() >= 40);
    let (mut rocky, mut vented) = (0, 0);
    for c in cases {
        let name = c["name"].as_str().unwrap();
        let seed: u64 = c["seed"].as_str().unwrap().parse().unwrap();
        let p = params(&c["params"]);
        let start = Instant::now();
        let (terrain, organic) = generate_terrain(&p, seed);
        if name == "largest" {
            println!(
                "largest ({}x{}, {} vents): {:?}",
                p.width,
                p.height,
                p.vent_count,
                start.elapsed()
            );
        }
        let label = format!("{name}, seed {seed}");
        assert_eq!(
            digest_bool(&terrain.rock),
            c["rock"].as_str().unwrap(),
            "rock of {label}"
        );
        assert_eq!(
            digest_f64(&terrain.chem),
            c["chem"].as_str().unwrap(),
            "chem of {label}"
        );
        assert_eq!(
            digest_f64(&terrain.sun),
            c["sun"].as_str().unwrap(),
            "sun of {label}"
        );
        assert_eq!(
            digest_f64(&organic),
            c["organic"].as_str().unwrap(),
            "organic of {label}"
        );
        rocky += usize::from(c["rock_tiles"].as_u64().unwrap() > 0);
        vented += usize::from(c["chem_tiles"].as_u64().unwrap() > 0);
    }
    // not vacuous: most cases have rock and vents
    assert!(
        rocky >= 30 && vented >= 30,
        "rocky {rocky}, vented {vented}"
    );
}

#[test]
fn plume_equals_python() {
    let v = vectors();
    let cases = v["plumes"].as_array().unwrap();
    assert!(cases.len() >= 27);
    for c in cases {
        let get = |k: &str| c[k].as_u64().unwrap() as usize;
        let (w, h, vx, vy) = (get("width"), get("height"), get("vx"), get("vy"));
        let (strength, radius) = (
            c["strength"].as_f64().unwrap(),
            c["radius"].as_f64().unwrap(),
        );
        let plume = vent_plume(h, w, vx, vy, strength, radius);
        assert_eq!(
            digest_f64(&plume),
            c["plume"].as_str().unwrap(),
            "plume {w}x{h} at ({vx}, {vy}), strength {strength}, radius {radius}"
        );
    }
}
