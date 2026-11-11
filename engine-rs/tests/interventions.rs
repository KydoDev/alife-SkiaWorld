//! ADR-0013 Decision 3: `World::intervene` refuses bad input before any write, so a refused edit leaves the
//! state hash, the terrain digest and the render (light) unchanged. Python has no reference for bad input, so
//! these are unit tests, not golden cases.

mod common;

use common::{golden_dir, render_digest, terrain_digest};
use worldsim_core::hash::state_hash;
use worldsim_core::save::load_world;
use worldsim_core::world::{
    Intervention, World, KIND_DIG, KIND_METEORITE, KIND_NUTRIENTS, KIND_RAISE_ROCK, KIND_VENT,
    MAX_EDIT_ORGANIC,
};

fn world(set: &str) -> World {
    load_world(golden_dir(set).join("start.json.gz")).expect("start save")
}

fn fingerprint(w: &World) -> (String, String, String) {
    (state_hash(w), terrain_digest(w), render_digest(w))
}

#[test]
fn records_with_a_bad_kind_or_a_used_unused_argument_are_refused() {
    let bad = [
        (0, 0, 0.0, "unknown intervention kind 0"),
        (6, 0, 0.0, "unknown intervention kind 6"),
        (u32::MAX, 0, 0.0, "unknown intervention kind"),
        (KIND_METEORITE, 2, 1.0, "amount must be 0"),
        (KIND_RAISE_ROCK, 2, -0.0, "amount must be 0"),
        (KIND_DIG, 2, f64::NAN, "amount must be 0"),
        (KIND_VENT, 1, 4.0, "radius must be 0 for a vent"),
    ];
    for (kind, radius, amount, msg) in bad {
        let err = Intervention::from_raw(kind, 1, 1, radius, amount).expect_err("accepted");
        assert!(err.message().contains(msg), "{kind}: {}", err.message());
    }
    assert!(Intervention::from_raw(KIND_METEORITE, 1, 1, 2, 0.0).is_ok());
    assert!(Intervention::from_raw(KIND_VENT, 1, 1, 0, 4.0).is_ok());
}

#[test]
fn a_refused_edit_changes_nothing() {
    for set in ["default", "volcanic"] {
        let mut w = world(set);
        let (x_out, y_out) = (w.width as u32, w.height as u32);
        let bad = [
            Intervention::Meteorite {
                x: x_out,
                y: 0,
                radius: 3,
            },
            Intervention::Dig {
                x: 0,
                y: y_out,
                radius: 3,
            },
            Intervention::Vent {
                x: u32::MAX,
                y: u32::MAX,
                max_chem: 4.0,
            },
            Intervention::Nutrients {
                x: 3,
                y: 3,
                radius: 2,
                amount: f64::NAN,
            },
            Intervention::Nutrients {
                x: 3,
                y: 3,
                radius: 2,
                amount: f64::INFINITY,
            },
            Intervention::Nutrients {
                x: 3,
                y: 3,
                radius: 2,
                amount: -1.0,
            },
            Intervention::Nutrients {
                x: 3,
                y: 3,
                radius: 2,
                amount: -0.0,
            },
            Intervention::Vent {
                x: 3,
                y: 3,
                max_chem: f64::NAN,
            },
            Intervention::Vent {
                x: 3,
                y: 3,
                max_chem: f64::NEG_INFINITY,
            },
            Intervention::Vent {
                x: 3,
                y: 3,
                max_chem: -0.0,
            },
        ];
        let before = fingerprint(&w);
        for iv in bad {
            let err = w.intervene(iv).expect_err("accepted");
            assert!(!err.message().is_empty());
            assert_eq!(fingerprint(&w), before, "{set}: {iv:?} changed the world");
        }
        // a refused world still steps like an untouched one
        let mut fresh = world(set);
        w.step();
        fresh.step();
        assert_eq!(state_hash(&w), state_hash(&fresh), "{set}");
    }
}

#[test]
fn a_nutrient_overflow_is_refused_before_any_tile_changes() {
    let mut w = world("default");
    let big = Intervention::Nutrients {
        x: 5,
        y: 5,
        radius: 0,
        amount: 0.5 * MAX_EDIT_ORGANIC,
    };
    assert_eq!(w.intervene(big), Ok(1));
    let before = fingerprint(&w);
    // the disc of radius 3 holds one tile that would pass the cap and many that would not: none may change
    let err = w
        .intervene(Intervention::Nutrients {
            x: 5,
            y: 5,
            radius: 3,
            amount: 0.6 * MAX_EDIT_ORGANIC,
        })
        .expect_err("overflow accepted");
    assert!(err.message().contains("above"), "{}", err.message());
    assert_eq!(fingerprint(&w), before);
    for amount in [f64::MAX, MAX_EDIT_ORGANIC] {
        let edit = Intervention::Nutrients {
            x: 30,
            y: 30,
            radius: 1,
            amount,
        };
        assert!(w.intervene(edit).is_err(), "{amount} accepted");
    }
}

#[test]
fn the_largest_accepted_nutrients_keep_every_later_step_finite() {
    // regression (piece 4 security review): an edit just under f64::MAX passed a "finite now" check and the
    // next step's diffusion overflowed; at the cap, the whole world stepped on stays finite
    let mut w = world("default");
    let whole = (w.width + w.height) as u32;
    let top = w.organic.iter().copied().fold(0.0, f64::max);
    let edit = Intervention::Nutrients {
        x: 0,
        y: 0,
        radius: whole,
        amount: MAX_EDIT_ORGANIC - top,
    };
    assert!(w.intervene(edit).unwrap() > 0);
    for _ in 0..50 {
        w.step();
        assert!(
            w.organic.iter().all(|o| o.is_finite()),
            "step {}",
            w.step_count
        );
        assert!(
            w.cells().all(|c| c.energy.is_finite()),
            "step {}",
            w.step_count
        );
    }
}

#[test]
fn a_radius_beyond_the_world_equals_the_whole_world() {
    for set in ["volcanic", "combined_width2"] {
        let base = world(set);
        let whole = (base.width + base.height) as u32;
        let edits = |r: u32| {
            [
                Intervention::Nutrients {
                    x: 1,
                    y: 1,
                    radius: r,
                    amount: 2.5,
                },
                Intervention::Meteorite {
                    x: 0,
                    y: 3,
                    radius: r,
                },
                Intervention::RaiseRock {
                    x: 1,
                    y: 0,
                    radius: r,
                },
                Intervention::Dig {
                    x: 0,
                    y: 0,
                    radius: r,
                },
            ]
        };
        for (huge, exact) in edits(u32::MAX).into_iter().zip(edits(whole)) {
            let (mut a, mut b) = (base.clone(), base.clone());
            assert_eq!(a.intervene(huge), b.intervene(exact), "{set}: {exact:?}");
            assert_eq!(fingerprint(&a), fingerprint(&b), "{set}: {exact:?}");
        }
    }
}

#[test]
fn edits_draw_nothing_from_the_rng() {
    let mut w = world("volcanic");
    let rng = w.rng.clone();
    for kind in [
        KIND_NUTRIENTS,
        KIND_METEORITE,
        KIND_RAISE_ROCK,
        KIND_DIG,
        KIND_VENT,
    ] {
        let (radius, amount) = match kind {
            KIND_NUTRIENTS => (4, 15.0),
            KIND_VENT => (0, 4.0),
            _ => (4, 0.0),
        };
        let iv = Intervention::from_raw(kind, 20, 10, radius, amount).unwrap();
        w.intervene(iv).unwrap();
    }
    assert_eq!(format!("{:?}", w.rng), format!("{rng:?}"));
}
