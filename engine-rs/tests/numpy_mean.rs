//! ADR-0012 piece 2: `numpy_mean` equals numpy's `ndarray.mean()` (pairwise summation) bit for bit on the
//! lengths of `scripts/g2_mean_vectors.py`, around every block boundary; the data is rebuilt here from the
//! same seeded generator with the same exact operations.

use serde_json::Value;
use worldsim_core::numpy::{numpy_mean, numpy_sum, pairwise};
use worldsim_core::rng::PyRandom;

fn f64_from_hex(s: &str) -> f64 {
    let mut bytes = [0u8; 8];
    for (k, b) in bytes.iter_mut().enumerate() {
        *b = u8::from_str_radix(&s[2 * k..2 * k + 2], 16).expect("hex");
    }
    f64::from_le_bytes(bytes)
}

fn vectors() -> Value {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/mean_vectors.json");
    serde_json::from_str(&std::fs::read_to_string(path).expect("mean_vectors.json")).expect("json")
}

fn data(seed: u64, n: usize) -> Vec<f64> {
    let mut rng = PyRandom::from_seed_u64(seed);
    (0..n)
        .map(|_| rng.random() * rng.random() * 1000.0 + rng.random())
        .collect()
}

#[test]
fn mean_equals_numpy() {
    let v = vectors();
    let base = v["seed_base"].as_u64().unwrap();
    let cases = v["cases"].as_array().unwrap();
    assert!(cases.len() >= 30);
    for c in cases {
        let n = c["n"].as_u64().unwrap() as usize;
        let a = data(base + n as u64, n);
        let (sum, mean) = (
            f64_from_hex(c["sum"].as_str().unwrap()),
            f64_from_hex(c["mean"].as_str().unwrap()),
        );
        assert_eq!(numpy_sum(&a).to_bits(), sum.to_bits(), "sum, n = {n}");
        assert_eq!(numpy_mean(&a).to_bits(), mean.to_bits(), "mean, n = {n}");
    }
}

/// The vectors are not vacuous: they tell numpy's accumulator seed (the identity) from the first
/// element, and pairwise from a plain left-to-right sum.
#[test]
fn the_vectors_tell_the_candidates_apart() {
    let v = vectors();
    let base = v["seed_base"].as_u64().unwrap();
    let (mut first_differs, mut plain_differs) = (0, 0);
    for c in v["cases"].as_array().unwrap() {
        let n = c["n"].as_u64().unwrap() as usize;
        let a = data(base + n as u64, n);
        let sum = f64_from_hex(c["sum"].as_str().unwrap());
        first_differs += usize::from((a[0] + pairwise(&a[1..])).to_bits() != sum.to_bits());
        plain_differs += usize::from(a.iter().sum::<f64>().to_bits() != sum.to_bits());
    }
    println!("first-element seed differs on {first_differs}, plain sum on {plain_differs}");
    assert!(first_differs > 0 && plain_differs > 0);
}
