//! M1a: the golden vectors written by `scripts/g2_golden.py` are present and well formed.
//! Later milestones compare the kernel against them (docs/G2_PLAN.md).

use std::fs;
use std::path::PathBuf;

fn golden_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/golden/default")
}

#[test]
fn hashes_csv_is_well_formed() {
    let text = fs::read_to_string(golden_dir().join("hashes.csv")).expect("hashes.csv missing");
    let mut lines = text.lines();
    assert_eq!(lines.next(), Some("step,population,hash"));
    let mut prev: Option<u64> = None;
    let mut rows = 0;
    for line in lines {
        let fields: Vec<&str> = line.split(',').collect();
        assert_eq!(fields.len(), 3, "bad row: {line}");
        let step: u64 = fields[0].parse().expect("step is not an integer");
        let _population: u64 = fields[1].parse().expect("population is not an integer");
        assert_eq!(fields[2].len(), 64, "hash is not SHA-256 hex: {line}");
        assert!(fields[2].bytes().all(|b| b.is_ascii_hexdigit()));
        if let Some(p) = prev {
            assert_eq!(step, p + 1, "steps must be consecutive");
        }
        prev = Some(step);
        rows += 1;
    }
    assert!(rows >= 2, "need the start hash and at least one step");
}

#[test]
fn start_save_is_gzip_and_rng_vectors_exist() {
    let save = fs::read(golden_dir().join("start.json.gz")).expect("start.json.gz missing");
    assert_eq!(&save[..2], &[0x1f, 0x8b], "start save is not gzip");
    let rng = fs::read_to_string(golden_dir().join("rng.json")).expect("rng.json missing");
    assert!(
        rng.contains("\"save_version\":5"),
        "golden save version must match the kernel"
    );
    assert_eq!(worldsim_core::SAVE_VERSION, 5);
}
