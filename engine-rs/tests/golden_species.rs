//! ADR-0018 piece 2: the kernel's species tracker equals `worldsim/species.py`. Each case of
//! `scripts/g3_species_vectors.py` (`species.json` in the golden root, regenerated on Linux by CI) creates a world
//! from its config and seed, or loads the tracked save `species_start.json.gz`, steps it (with a game and its
//! meteorites where the case has one) and must give, every 100 steps, the same state hash (also the untracked
//! one: the tracker is an observer), tracker digest, cells digest and tile-words hash, and at the end the same
//! tracker, field by field, and the same species for every cell. Then the loader's refusals of a bad tracker.

mod common;

use common::{game_rules_of, golden_root};
use flate2::read::GzDecoder;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::io::Read;
use worldsim_core::game::{Game, Tool};
use worldsim_core::hash::state_hash;
use worldsim_core::save::{config_from_json, load_world, world_from_json};
use worldsim_core::species::{Species, SpeciesTracker};
use worldsim_core::views::{tile_words, tiles_len};
use worldsim_core::world::World;

const CASES: [&str; 6] = [
    "created_default",
    "created_volcanic",
    "created_flags",
    "created_reseed",
    "tracked_save",
    "game_meteorites",
];

fn vectors() -> Value {
    let path = golden_root().join("species.json");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).expect("species.json")
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn opt(v: Option<u64>) -> u64 {
    v.unwrap_or(u64::MAX)
}

/// The tracker digest of the generator's docstring.
fn tracker_digest(t: &SpeciesTracker) -> String {
    let c = t.counters();
    let mut h = Sha256::new();
    for v in [c.next_id, c.speciations, c.novelty, c.pruned] {
        h.update(v.to_le_bytes());
    }
    for s in t.species() {
        let fields = [
            s.id,
            s.parent.unwrap_or(0),
            u64::from(s.origin.code()),
            s.born,
            opt(s.extinct),
            s.count,
            s.peak,
            s.activity,
            opt(s.established),
            s.children,
        ];
        for v in fields {
            h.update(v.to_le_bytes());
        }
        for g in s.founder_genes {
            h.update(g.to_le_bytes());
        }
    }
    hex(&h.finalize())
}

fn cells_by_id(world: &World) -> Vec<(u64, u64)> {
    let mut cells: Vec<(u64, u64)> = world.cells().map(|c| (c.id, c.species)).collect();
    cells.sort_unstable();
    cells
}

fn cells_digest(world: &World) -> String {
    let mut h = Sha256::new();
    for (id, species) in cells_by_id(world) {
        h.update(id.to_le_bytes());
        h.update(species.to_le_bytes());
    }
    hex(&h.finalize())
}

fn tiles_digest(world: &World) -> String {
    let mut out = vec![0u8; tiles_len(world)];
    tile_words(world, &mut out);
    hex(&Sha256::digest(&out))
}

fn start_world(case: &Value) -> World {
    if case["config"].is_null() {
        let save = case["save"].as_str().expect("save");
        return load_world(golden_root().join(save)).expect("tracked save");
    }
    let cfg = config_from_json(&serde_json::to_vec(&case["config"]).unwrap()).expect("config");
    let seed: u64 = case["seed"].as_str().unwrap().parse().expect("seed");
    World::new(cfg, seed)
}

/// The final tracker against the dump, field by field (a mismatch names the species and the field).
fn assert_same_tracker(name: &str, t: &SpeciesTracker, d: &Value) {
    let c = t.counters();
    let counters = [
        ("next_id", c.next_id),
        ("speciations", c.speciations),
        ("novelty", c.novelty),
        ("pruned", c.pruned),
    ];
    for (key, v) in counters {
        assert_eq!(v, d[key].as_u64().unwrap(), "{name}: tracker {key}");
    }
    let rows = d["species"].as_array().unwrap();
    let species: Vec<&Species> = t.species();
    assert_eq!(species.len(), rows.len(), "{name}: retained species");
    for (s, row) in species.iter().zip(rows) {
        let r = row.as_array().unwrap();
        let id = s.id;
        assert_eq!(id, r[0].as_u64().unwrap(), "{name}: species ids");
        assert_eq!(s.parent, r[1].as_u64(), "{name}: species #{id} parent");
        assert_eq!(
            s.origin.name(),
            r[2].as_str().unwrap(),
            "{name}: species #{id} origin"
        );
        let genes: Vec<String> = s
            .founder_genes
            .iter()
            .map(|g| hex(&g.to_le_bytes()))
            .collect();
        let want: Vec<&str> = r[3]
            .as_array()
            .unwrap()
            .iter()
            .map(|g| g.as_str().unwrap())
            .collect();
        assert_eq!(genes, want, "{name}: species #{id} founder genes");
        let fields = [
            ("born", Some(s.born), &r[4]),
            ("extinct", s.extinct, &r[5]),
            ("count", Some(s.count), &r[6]),
            ("peak", Some(s.peak), &r[7]),
            ("activity", Some(s.activity), &r[8]),
            ("established", s.established, &r[9]),
            ("children", Some(s.children), &r[10]),
        ];
        for (field, v, want) in fields {
            assert_eq!(v, want.as_u64(), "{name}: species #{id} {field}");
        }
    }
}

#[test]
fn trackers_equal_python() {
    let doc = vectors();
    let cases = doc["cases"].as_array().unwrap();
    let names: Vec<&str> = cases.iter().map(|c| c["name"].as_str().unwrap()).collect();
    assert_eq!(names, CASES);
    let every = doc["sample_every"].as_u64().unwrap();
    for case in cases {
        let name = case["name"].as_str().unwrap();
        let mut world = start_world(case);
        let mut twin = world.clone();
        twin.drop_tracker();
        for _ in 0..case["warmup"].as_u64().unwrap() {
            world.step();
            twin.step();
        }
        let mut game = (!case["rules"].is_null()).then(|| {
            let rules = game_rules_of(&case["rules"]);
            (
                Game::new(&world, rules.clone()).unwrap(),
                Game::new(&twin, rules).unwrap(),
            )
        });
        let mut actions: Vec<&Value> = case["actions"].as_array().unwrap().iter().collect();
        actions.sort_by_key(|a| a[0].as_u64().unwrap()); // stable, as Python's sorted
        let mut actions = actions.into_iter().peekable();
        assert_eq!(
            world.step_count,
            case["start_step"].as_u64().unwrap(),
            "{name}: start"
        );
        let steps = case["steps"].as_u64().unwrap();
        let mut samples = case["samples"].as_array().unwrap().iter();
        for k in 0..=steps {
            while let Some(a) = actions.next_if(|a| a[0].as_u64().unwrap() <= k) {
                let tool = Tool::from_name(a[1].as_str().unwrap()).expect("tool");
                let (x, y) = (a[2].as_u64().unwrap() as u32, a[3].as_u64().unwrap() as u32);
                let (g, gt) = game.as_mut().expect("actions need a game");
                g.act(&mut world, tool, x, y).unwrap();
                gt.act(&mut twin, tool, x, y).unwrap();
            }
            if k % every == 0 || k == steps {
                let want = samples
                    .next()
                    .unwrap_or_else(|| panic!("{name}: too few samples"));
                let step = world.step_count;
                assert_eq!(step, want["step"].as_u64().unwrap(), "{name}: sample step");
                let hash = state_hash(&world);
                assert_eq!(
                    hash,
                    want["hash"].as_str().unwrap(),
                    "{name}: state hash at {step}"
                );
                assert_eq!(
                    hash,
                    state_hash(&twin),
                    "{name}: the tracker changed the history at {step}"
                );
                let t = world.tracker().expect("tracked");
                assert_eq!(
                    tracker_digest(t),
                    want["tracker"].as_str().unwrap(),
                    "{name}: tracker at {step}"
                );
                assert_eq!(
                    cells_digest(&world),
                    want["cells"].as_str().unwrap(),
                    "{name}: cells at {step}"
                );
                assert_eq!(
                    tiles_digest(&world),
                    want["tiles"].as_str().unwrap(),
                    "{name}: tiles at {step}"
                );
            }
            if k < steps {
                match game.as_mut() {
                    Some((g, gt)) => {
                        g.step(&mut world);
                        gt.step(&mut twin);
                    }
                    None => {
                        world.step();
                        twin.step();
                    }
                }
            }
        }
        assert!(samples.next().is_none(), "{name}: too many samples");
        assert_same_tracker(name, world.tracker().unwrap(), &case["tracker"]);
        let want: Vec<(u64, u64)> = case["cells"]
            .as_array()
            .unwrap()
            .iter()
            .map(|p| (p[0].as_u64().unwrap(), p[1].as_u64().unwrap()))
            .collect();
        assert_eq!(cells_by_id(&world), want, "{name}: cells' species");
    }
}

// ------------------------------------------------------------------ loading

fn start_save_json() -> Value {
    let path = golden_root().join(vectors()["start_save"].as_str().unwrap());
    let mut text = String::new();
    GzDecoder::new(std::fs::File::open(&path).expect("tracked save"))
        .read_to_string(&mut text)
        .expect("gzip");
    serde_json::from_str(&text).expect("save json")
}

fn load(save: &Value) -> Result<World, String> {
    world_from_json(&serde_json::to_vec(save).unwrap()).map_err(|e| e.message().to_string())
}

#[test]
fn a_tracked_save_loads_its_tracker_and_an_untracked_one_has_none() {
    let save = start_save_json();
    let world = load(&save).unwrap();
    let t = world.tracker().expect("tracker");
    assert_eq!(
        t.counters().next_id,
        save["tracker"]["next_id"].as_u64().unwrap()
    );
    assert!(world
        .cells()
        .all(|c| t.get(c.species).is_some_and(|s| s.extinct.is_none())));
    let mut untracked = save.clone();
    untracked["tracker"] = Value::Null;
    let world = load(&untracked).unwrap();
    assert!(world.tracker().is_none());
    assert!(
        world.cells().all(|c| c.species == 0),
        "species ids dropped without a tracker"
    );
    let mut missing = save;
    missing.as_object_mut().unwrap().remove("tracker");
    assert!(
        load(&missing).is_err(),
        "the tracker key is required (null when untracked)"
    );
}

#[test]
fn bad_trackers_are_refused() {
    let save = start_save_json();
    let extant = |s: &Value| -> usize {
        let rows = s["tracker"]["species"].as_array().unwrap();
        rows.iter()
            .position(|r| r[5].is_null() && r[6].as_u64().unwrap() > 1)
            .unwrap()
    };
    let i = extant(&save);
    let first_cell_species = save["cells"][0][7].as_u64().unwrap();
    type Edit = Box<dyn Fn(&mut Value)>;
    let cases: Vec<(&str, Edit, &str)> = vec![
        (
            "count",
            Box::new(move |s| {
                s["tracker"]["species"][i][6] =
                    (s["tracker"]["species"][i][6].as_u64().unwrap() + 1).into()
            }),
            "members",
        ),
        (
            "origin",
            Box::new(move |s| s["tracker"]["species"][i][2] = "alien".into()),
            "origin",
        ),
        (
            "genes",
            Box::new(move |s| s["tracker"]["species"][i][3][0] = 1.5.into()),
            "founder genome",
        ),
        (
            "short genome",
            Box::new(move |s| {
                s["tracker"]["species"][i][3].as_array_mut().unwrap().pop();
            }),
            "",
        ),
        (
            "id above next_id",
            Box::new(|s| s["tracker"]["next_id"] = 1.into()),
            "outside",
        ),
        (
            "params",
            Box::new(|s| s["tracker"]["threshold"] = 0.31.into()),
            "parameters",
        ),
        (
            "prune peak",
            Box::new(|s| s["tracker"]["prune_peak"] = 6.into()),
            "parameters",
        ),
        (
            "cell species",
            Box::new(|s| s["cells"][0][7] = 0.into()),
            "unknown or extinct",
        ),
        (
            "huge count",
            Box::new(|s| s["tracker"]["pruned"] = (1u64 << 63).into()),
            "2^62",
        ),
        (
            "extinct with members",
            Box::new(move |s| s["tracker"]["species"][i][5] = 10.into()),
            "count or extinction",
        ),
        (
            "duplicate",
            Box::new(|s| {
                let row = s["tracker"]["species"][0].clone();
                s["tracker"]["species"].as_array_mut().unwrap().push(row);
            }),
            "duplicate",
        ),
        (
            "children",
            Box::new(move |s| s["tracker"]["species"][i][10] = 99.into()),
            "children",
        ),
        (
            "negative",
            Box::new(|s| s["tracker"]["novelty"] = (-1).into()),
            "",
        ),
    ];
    for (what, edit, message) in cases {
        let mut bad = save.clone();
        edit(&mut bad);
        let e = load(&bad).expect_err(what);
        assert!(e.contains(message), "{what}: {e}");
    }
    assert_ne!(first_cell_species, 0);
}
