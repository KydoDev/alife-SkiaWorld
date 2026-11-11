//! M5 (F5a): `genome_distance` equals Python's (`math.dist` x sqrt(10 / 16)) bit for bit on the
//! pairs written by `scripts/g2_distance_vectors.py`. `math.dist` is CPython's own extended-precision
//! algorithm, not a libm call, so it is the same on every platform: one committed file serves all.

use serde_json::Value;
use worldsim_core::world::genome_distance;
use worldsim_core::N_GENES;

fn f64_from_hex(s: &str) -> f64 {
    let mut bytes = [0u8; 8];
    for (k, b) in bytes.iter_mut().enumerate() {
        *b = u8::from_str_radix(&s[2 * k..2 * k + 2], 16).expect("hex");
    }
    f64::from_le_bytes(bytes)
}

fn genes(v: &Value) -> [f64; N_GENES] {
    let list = v.as_array().expect("gene list");
    assert_eq!(list.len(), N_GENES);
    let mut g = [0.0; N_GENES];
    for (o, s) in g.iter_mut().zip(list) {
        *o = f64_from_hex(s.as_str().expect("hex string"));
    }
    g
}

#[test]
fn genome_distance_equals_python() {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/genome_distance.json");
    let data: Value =
        serde_json::from_str(&std::fs::read_to_string(path).expect("genome_distance.json"))
            .expect("json");
    let pairs = data["pairs"].as_array().expect("pairs");
    assert!(pairs.len() >= 100);
    for (k, p) in pairs.iter().enumerate() {
        let want = f64_from_hex(p["d"].as_str().expect("d"));
        let got = genome_distance(&genes(&p["a"]), &genes(&p["b"]));
        assert_eq!(
            got.to_bits(),
            want.to_bits(),
            "pair {k}: {got:e} vs {want:e}"
        );
    }
}
