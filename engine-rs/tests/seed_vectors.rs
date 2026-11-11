//! ADR-0012 piece 1: `PyRandom::from_seed_u64` / `from_seed_str` equal CPython's `random.Random(seed)`:
//! the full state (624 words + index, no cached gauss) and the first draws, on the seeds written by
//! `scripts/g2_seed_vectors.py`. Seeding is integer arithmetic and SHA-512, the same on every platform.

use serde_json::Value;
use sha2::{Digest, Sha256};
use worldsim_core::rng::PyRandom;

#[test]
fn seeding_equals_cpython() {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/seed_vectors.json");
    let data: Value =
        serde_json::from_str(&std::fs::read_to_string(path).expect("seed_vectors.json"))
            .expect("json");
    let draws = data["draws"].as_u64().expect("draws");
    let cases = data["cases"].as_array().expect("cases");
    assert!(cases.len() >= 13);
    for c in cases {
        let seed = c["seed"].as_str().expect("seed");
        let mut rng = match c["kind"].as_str().expect("kind") {
            "int" => PyRandom::from_seed_u64(seed.parse().expect("u64 seed")),
            "str" => PyRandom::from_seed_str(seed),
            k => panic!("unknown kind {k}"),
        };
        let want: Vec<u32> = c["state"]
            .as_array()
            .expect("state")
            .iter()
            .map(|w| w.as_u64().expect("word") as u32)
            .collect();
        let (words, gauss_next) = rng.state();
        assert_eq!(words, want, "state of seed {seed:?}");
        assert_eq!(gauss_next, None);
        let mut h = Sha256::new();
        for _ in 0..draws {
            h.update(rng.random().to_le_bytes());
        }
        let got: String = h.finalize().iter().map(|b| format!("{b:02x}")).collect();
        assert_eq!(
            got,
            c["draws_sha256"].as_str().unwrap(),
            "draws of seed {seed:?}"
        );
    }
}
