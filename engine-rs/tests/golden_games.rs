//! ADR-0017 piece 2: the kernel's `Game` equals `play.Game`. Each case of `scripts/g3_game_vectors.py`
//! (`games.json` in the golden root, regenerated on Linux by CI) loads a golden start save, attaches a game with
//! the case's rules and applies its action log at its step offsets; per action whether it was accepted and the
//! budget after it, then the milestones reached and their steps, the state hash every 100 steps, the final budget
//! and the player's vents must all be equal, and at every milestone check what the check measures (the trace).

mod common;

use common::{game_rules_of as rules_of, golden_dir, golden_root, hashes};
use serde_json::Value;
use worldsim_core::game::{Game, GameRules, Measures, Milestone, Tool};
use worldsim_core::hash::state_hash;
use worldsim_core::save::load_world;
use worldsim_core::world::World;

const CASES: [&str; 8] = [
    "idle_default",
    "idle_volcanic",
    "budget",
    "abyss_balance_giant",
    "plastic_abyss_giant",
    "survivor",
    "strike_window",
    "divided",
];

fn vectors() -> Value {
    let path = golden_root().join("games.json");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).expect("games.json")
}

fn f64_hex(v: f64) -> String {
    v.to_le_bytes().iter().map(|b| format!("{b:02x}")).collect()
}

/// Bitwise equality, so `-0.0` and `0.0` (or two NaNs) are told apart.
fn same_rules(a: &GameRules, b: &GameRules) -> bool {
    let bits = |r: &GameRules| {
        let mut v = vec![
            r.budget_max,
            r.budget_start,
            r.regen,
            r.nutrients_amount,
            r.max_chem,
            r.abyss_radius,
            r.kill_fraction,
            r.recover_fraction,
        ];
        v.extend(r.cost);
        v.iter().map(|x| x.to_bits()).collect::<Vec<u64>>()
    };
    bits(a) == bits(b)
        && (a.radius, a.check_every, a.abyss_cells, a.balance_cells)
            == (b.radius, b.check_every, b.abyss_cells, b.balance_cells)
        && (a.giant_colony, a.collapse_window, a.divided_cells)
            == (b.giant_colony, b.collapse_window, b.divided_cells)
}

#[test]
fn tool_and_milestone_names_equal_python() {
    let v = vectors();
    let tools: Vec<&str> = Tool::ALL.iter().map(|t| t.name()).collect();
    let milestones: Vec<&str> = Milestone::ALL.iter().map(|m| m.name()).collect();
    let py = |key: &str| -> Vec<String> {
        v[key]
            .as_array()
            .unwrap()
            .iter()
            .map(|s| s.as_str().unwrap().to_string())
            .collect()
    };
    assert_eq!(py("tools"), tools);
    assert_eq!(py("milestones"), milestones);
}

#[test]
fn default_rules_equal_python() {
    let v = vectors();
    let python = rules_of(&v["default_rules"]);
    assert!(
        same_rules(&python, &GameRules::default()),
        "GameRules::default() differs from Python's GameRules():\n{python:?}\n{:?}",
        GameRules::default()
    );
}

/// One trace entry of the vector script, as the kernel's `Measures`.
fn measures_of(t: &Value) -> Measures {
    let counts = |key: &str| -> Vec<u64> {
        t[key]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_u64().unwrap())
            .collect()
    };
    let bits = |v: &Value| {
        let bytes: Vec<u8> = (0..8)
            .map(|i| u8::from_str_radix(&v.as_str().unwrap()[2 * i..2 * i + 2], 16).unwrap())
            .collect();
        f64::from_le_bytes(bytes.try_into().unwrap())
    };
    Measures {
        near_vents: t["near"].as_u64().unwrap(),
        specialists: counts("specialists").try_into().expect("three strategies"),
        largest_colony: t["colony"].as_u64().unwrap(),
        cells_per_sea: counts("seas"),
        smoothed: bits(&t["smoothed"]),
        collapse_target: (!t["collapse"].is_null()).then(|| bits(&t["collapse"])),
        dipped: t["dipped"].as_bool().unwrap(),
    }
}

/// Floats compared by their bits.
fn same_measures(a: &Measures, b: &Measures) -> bool {
    let bits = |m: &Measures| (m.smoothed.to_bits(), m.collapse_target.map(f64::to_bits));
    (
        a.near_vents,
        a.specialists,
        a.largest_colony,
        &a.cells_per_sea,
        a.dipped,
    ) == (
        b.near_vents,
        b.specialists,
        b.largest_colony,
        &b.cells_per_sea,
        b.dipped,
    ) && bits(a) == bits(b)
}

/// The step-by-step replay of `run_case`: actions due at offset `k` run before the hash at `k` and the step.
fn run_case(case: &Value) {
    let name = case["name"].as_str().unwrap();
    let set = case["set"].as_str().unwrap();
    let mut world: World = load_world(golden_dir(set).join("start.json.gz")).expect("start save");
    let start = world.step_count;
    assert_eq!(
        start,
        case["start_step"].as_u64().unwrap(),
        "{name}: start step"
    );
    let rules = rules_of(&case["rules"]);
    let mut game = Game::new(&world, rules).unwrap_or_else(|e| panic!("{name}: rules: {e}"));
    let steps = case["steps"].as_u64().unwrap();
    let mut actions = case["actions"].as_array().unwrap().iter().peekable();
    let mut hashes = case["hashes"].as_array().unwrap().iter();
    let mut trace = case["trace"].as_array().unwrap().iter();
    let check_every = game.rules().check_every;
    let csv: Vec<(u64, u64, String)> = if name.starts_with("idle") {
        hashes_by_step(set)
    } else {
        Vec::new()
    };
    for k in 0..=steps {
        while let Some(a) = actions.next_if(|a| a["offset"].as_u64().unwrap() <= k) {
            let tool = Tool::from_name(a["tool"].as_str().unwrap()).expect("tool name");
            let (x, y) = (a["x"].as_u64().unwrap(), a["y"].as_u64().unwrap());
            let accepted = game
                .act(&mut world, tool, x as u32, y as u32)
                .unwrap_or_else(|e| panic!("{name}: {a}: refused by the kernel: {e}"));
            assert_eq!(
                (accepted, f64_hex(game.budget())),
                (
                    a["accepted"].as_bool().unwrap(),
                    a["budget"].as_str().unwrap().to_string()
                ),
                "{name} at offset {k}: {a}: accepted, budget"
            );
        }
        if k % 100 == 0 || k == steps {
            let want = hashes
                .next()
                .unwrap_or_else(|| panic!("{name}: no hash for offset {k}"));
            assert_eq!(
                (world.step_count, state_hash(&world)),
                (
                    want[0].as_u64().unwrap(),
                    want[1].as_str().unwrap().to_string()
                ),
                "{name}: state hash at offset {k}"
            );
        }
        if !csv.is_empty() {
            // an idle game leaves the world's history alone: every step equals the set's hashes.csv
            let row = &csv[usize::try_from(k).unwrap()];
            assert_eq!(
                (row.0, row.2.as_str()),
                (world.step_count, state_hash(&world).as_str()),
                "{name}: hashes.csv at step {}",
                world.step_count
            );
        }
        if k < steps {
            game.step(&mut world);
            if world.step_count.is_multiple_of(check_every) {
                let want = trace
                    .next()
                    .unwrap_or_else(|| panic!("{name}: no trace at offset {k}"));
                assert_eq!(
                    world.step_count,
                    want["step"].as_u64().unwrap(),
                    "{name}: trace step"
                );
                let (got, want) = (game.measures(&world), measures_of(want));
                assert!(
                    same_measures(&got, &want),
                    "{name} at step {}: measures
 kernel {got:?}
 python {want:?}",
                    world.step_count
                );
            }
        }
    }
    assert!(trace.next().is_none(), "{name}: trace after the last step");
    assert!(
        actions.next().is_none(),
        "{name}: actions after the last step"
    );
    assert!(
        hashes.next().is_none(),
        "{name}: hashes after the last step"
    );
    let achieved = &case["achieved"];
    for m in Milestone::ALL {
        assert_eq!(
            game.achieved(m),
            achieved[m.name()].as_u64(),
            "{name}: milestone {}",
            m.name()
        );
    }
    assert_eq!(
        f64_hex(game.budget()),
        case["budget"].as_str().unwrap(),
        "{name}: final budget"
    );
    assert_eq!(
        game.player_vents() as u64,
        case["player_vents"].as_u64().unwrap(),
        "{name}: player vents"
    );
}

/// The set's `hashes.csv` rows, checked to be one per step from the start.
fn hashes_by_step(set: &str) -> Vec<(u64, u64, String)> {
    let rows = hashes(set);
    for (i, w) in rows.windows(2).enumerate() {
        assert_eq!(
            w[1].0,
            w[0].0 + 1,
            "{set}: hashes.csv row {i} is not one step"
        );
    }
    rows
}

#[test]
fn games_equal_python() {
    let v = vectors();
    let cases = v["cases"].as_array().unwrap();
    let names: Vec<&str> = cases.iter().map(|c| c["name"].as_str().unwrap()).collect();
    assert_eq!(names, CASES);
    for case in cases {
        run_case(case);
    }
}

#[test]
fn a_kernel_refusal_leaves_the_game_unchanged() {
    let mut world = load_world(golden_dir("default").join("start.json.gz")).expect("start save");
    let rules = GameRules {
        nutrients_amount: 6e11, // two of these on one tile pass MAX_EDIT_ORGANIC
        ..GameRules::default()
    };
    let mut game = Game::new(&world, rules).expect("rules");
    assert_eq!(game.act(&mut world, Tool::Nutrients, 10, 10), Ok(true));
    let (budget, hash) = (game.budget(), state_hash(&world));
    assert!(game.act(&mut world, Tool::Nutrients, 10, 10).is_err());
    assert_eq!(game.budget().to_bits(), budget.to_bits());
    assert_eq!(state_hash(&world), hash);
}

#[test]
fn off_world_and_unaffordable_actions_are_refused_for_free() {
    let mut world = load_world(golden_dir("default").join("start.json.gz")).expect("start save");
    let mut game = Game::new(&world, GameRules::default()).expect("rules");
    let (w, h) = (world.width as u32, world.height as u32);
    assert_eq!(game.act(&mut world, Tool::Meteorite, w, 0), Ok(false));
    assert_eq!(game.act(&mut world, Tool::Meteorite, 0, h), Ok(false));
    assert_eq!(game.budget(), 100.0);
    for _ in 0..2 {
        assert_eq!(game.act(&mut world, Tool::Volcano, 40, 30), Ok(true));
    }
    assert_eq!(game.player_vents(), 1, "the same tile twice is one vent");
    assert_eq!(game.budget(), 20.0);
    assert_eq!(game.act(&mut world, Tool::Volcano, 50, 30), Ok(false));
    assert_eq!(game.budget(), 20.0);
}

#[test]
fn a_day_longer_than_the_smoothing_cap_is_refused() {
    use worldsim_core::game::MAX_SMOOTH_WINDOW;
    let mut world = load_world(golden_dir("default").join("start.json.gz")).expect("start save");
    world.cfg.day_amplitude = 0.5;
    world.cfg.day_length = MAX_SMOOTH_WINDOW;
    assert!(Game::new(&world, GameRules::default()).is_ok());
    world.cfg.day_length = MAX_SMOOTH_WINDOW + 1;
    let err = Game::new(&world, GameRules::default()).expect_err("refused");
    assert!(err.message().contains("day_length"), "{err}");
    world.cfg.day_amplitude = 0.0; // no days: a window of one step
    assert!(Game::new(&world, GameRules::default()).is_ok());
}

#[test]
fn rules_are_validated() {
    assert_eq!(GameRules::default().validate(), Ok(()));
    let bad = [
        GameRules {
            regen: f64::NAN,
            ..GameRules::default()
        },
        GameRules {
            budget_max: f64::INFINITY,
            ..GameRules::default()
        },
        GameRules {
            budget_start: -0.0,
            ..GameRules::default()
        },
        GameRules {
            kill_fraction: 2e12,
            ..GameRules::default()
        },
        GameRules {
            cost: [10.0, -1.0, 4.0, 4.0, 40.0],
            ..GameRules::default()
        },
        GameRules {
            radius: [6, 10, 2, 2_000_000, 0],
            ..GameRules::default()
        },
        GameRules {
            check_every: 0,
            ..GameRules::default()
        },
    ];
    let world = load_world(golden_dir("default").join("start.json.gz")).expect("start save");
    for rules in bad {
        let err = rules.validate().expect_err("refused");
        assert!(!err.message().is_empty());
        assert!(Game::new(&world, rules).is_err());
    }
}
