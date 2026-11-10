//! M1b: `PyRandom` reproduces every draw in the golden `rng.json` files bit-for-bit.
//!
//! The draws come from one CPython `random.Random(seed)` in a fixed order
//! (`scripts/g2_golden.py::rng_vectors`), so one generator consumes them all in that order.
//! Integer draws and `end_state` do not depend on the platform maths library; `gauss` does
//! (log/sqrt/cos/sin), so its comparison reports the first mismatch instead of a tolerance.

use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use worldsim_core::rng::{PyRandom, RngStateError};

const GOLDEN_SETS: [&str; 2] = ["default", "volcanic"];
/// `RANDRANGE_NS` of the generator script, in generation order (JSON object keys are unordered).
const RANDRANGE_NS: [u64; 10] = [
    1,
    2,
    3,
    7,
    10,
    100,
    1000,
    10_240,
    (1 << 31) - 1,
    (1 << 32) + 5,
];

fn load(set: &str) -> Value {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/golden")
        .join(set)
        .join("rng.json");
    serde_json::from_str(&fs::read_to_string(&path).expect("rng.json missing")).expect("bad JSON")
}

fn words(v: &Value) -> Vec<u32> {
    v.as_array()
        .expect("state is not an array")
        .iter()
        .map(|w| u32::try_from(w.as_u64().expect("state word")).expect("word > u32"))
        .collect()
}

fn ints(v: &Value) -> Vec<u64> {
    v.as_array()
        .expect("not an array")
        .iter()
        .map(|x| x.as_u64().expect("not an integer"))
        .collect()
}

/// A float stored by `struct.pack("<d", v).hex()`.
fn f64_from_hex(hex: &str) -> f64 {
    assert_eq!(hex.len(), 16, "bad float hex {hex}");
    let mut bytes = [0u8; 8];
    for (i, b) in bytes.iter_mut().enumerate() {
        *b = u8::from_str_radix(&hex[2 * i..2 * i + 2], 16).expect("bad hex digit");
    }
    f64::from_le_bytes(bytes)
}

fn start(golden: &Value) -> PyRandom {
    PyRandom::from_state(&words(&golden["start_state"]), None).expect("valid start state")
}

/// Bit-exact float comparison, reporting how many differ and where the first one is.
fn assert_floats(label: &str, got: &[f64], want: &[f64]) {
    assert_eq!(got.len(), want.len(), "{label}: length");
    let bad: Vec<usize> = (0..got.len())
        .filter(|&i| got[i].to_bits() != want[i].to_bits())
        .collect();
    if let Some(&i) = bad.first() {
        panic!(
            "{label}: {} of {} draws differ; first at {i}: got {:016x} ({:e}), want {:016x} ({:e})",
            bad.len(),
            got.len(),
            got[i].to_bits(),
            got[i],
            want[i].to_bits(),
            want[i]
        );
    }
}

#[test]
fn golden_stream_matches_cpython() {
    for set in GOLDEN_SETS {
        check_stream(set, &load(set));
    }
}

fn check_stream(set: &str, g: &Value) {
    let mut rng = start(g);

    let want: Vec<f64> = g["random"]
        .as_array()
        .unwrap()
        .iter()
        .map(|h| f64_from_hex(h.as_str().unwrap()))
        .collect();
    let got: Vec<f64> = (0..want.len()).map(|_| rng.random()).collect();
    assert_floats(&format!("{set}/random"), &got, &want);

    for n in RANDRANGE_NS {
        let want = ints(&g["randrange"][n.to_string()]);
        let got: Vec<u64> = (0..want.len()).map(|_| rng.randrange(n)).collect();
        assert_eq!(got, want, "{set}/randrange({n})");
    }

    for (i, want) in g["shuffle_50"].as_array().unwrap().iter().enumerate() {
        let mut xs: Vec<u64> = (0..50).collect();
        rng.shuffle(&mut xs);
        assert_eq!(xs, ints(want), "{set}/shuffle_50[{i}]");
    }

    let nine: Vec<u64> = (0..9).collect();
    let want = ints(&g["choice_9"]);
    let got: Vec<u64> = (0..want.len()).map(|_| *rng.choice(&nine)).collect();
    assert_eq!(got, want, "{set}/choice_9");

    // gauss and random interleaved: random() must leave a pending gauss_next untouched.
    let (mut got_g, mut want_g, mut got_r, mut want_r) = (vec![], vec![], vec![], vec![]);
    for entry in g["mixed_gauss_random"].as_array().unwrap() {
        let kind = entry[0].as_str().unwrap();
        let want = f64_from_hex(entry[1].as_str().unwrap());
        match kind {
            "g" => {
                got_g.push(rng.gauss(0.0, 0.05));
                want_g.push(want);
            }
            "r" => {
                got_r.push(rng.random());
                want_r.push(want);
            }
            other => panic!("unknown draw kind {other}"),
        }
    }
    // Integer state first: it is independent of the maths library, so it is checked even if
    // gauss differs by an ULP on another platform.
    let (state, _) = rng.state();
    assert_eq!(state, words(&g["end_state"]), "{set}/end_state");
    assert_floats(&format!("{set}/mixed random"), &got_r, &want_r);
    assert_floats(&format!("{set}/mixed gauss"), &got_g, &want_g);
}

#[test]
fn restored_mid_stream_state_continues_identically() {
    let mut a = start(&load("default"));
    for _ in 0..3 {
        a.gauss(0.0, 1.0);
    }
    a.random();
    a.randrange(10_240);
    let (words, gauss_next) = a.state();
    assert!(
        gauss_next.is_some(),
        "an odd number of gauss calls leaves a cached value"
    );
    let mut b = PyRandom::from_state(&words, gauss_next).unwrap();
    for _ in 0..2000 {
        assert_eq!(a.gauss(0.0, 1.0).to_bits(), b.gauss(0.0, 1.0).to_bits());
        assert_eq!(a.random().to_bits(), b.random().to_bits());
        assert_eq!(a.getrandbits(64), b.getrandbits(64));
    }
    assert_eq!(a, b);
}

#[test]
fn invalid_states_are_rejected() {
    assert_eq!(
        PyRandom::from_state(&[0; 624], None),
        Err(RngStateError::WrongLength(624))
    );
    let mut words = vec![0u32; 625];
    words[624] = 625;
    assert_eq!(
        PyRandom::from_state(&words, None),
        Err(RngStateError::BadIndex(625))
    );
    words[624] = 624;
    assert!(PyRandom::from_state(&words, None).is_ok());
}
