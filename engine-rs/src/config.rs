//! Simulation parameters, read from a save and validated like `worldsim/config.py`.
//!
//! Every field of the Python `Config` dataclass is declared once in [`config_fields!`] with its
//! type and its `Config.validate()` bounds, so the two lists can be compared line by line. A save
//! must name every field and nothing else: a key the kernel does not know is an error (it could
//! be a rule this kernel does not implement), and so is a missing one (Python would fill in its
//! own default, which the kernel does not duplicate).

use crate::SaveError;
use serde_json::{Map, Value};

/// `worldsim/config.py::MAX_WORLD_TILES`: width * height cap for any world.
pub const MAX_WORLD_TILES: i64 = 1_000_000;

const INF: f64 = f64::INFINITY;

/// Declares `Config` and its parser. Each line: `name: kind [lo, hi]`, `kind` one of `f64`,
/// `i64`, `bool`; bounds are inclusive and mirror `_BOUNDS` (default `[0, inf]`).
macro_rules! config_fields {
    ($($name:ident : $kind:ident $([$lo:expr, $hi:expr])?),* $(,)?) => {
        /// The Python `Config`, field for field (`worldsim/config.py`).
        #[derive(Debug, Clone, PartialEq)]
        pub struct Config {
            $(pub $name: $kind,)*
        }

        impl Config {
            /// Field names in declaration order (the order of `Config.to_dict()`).
            pub const FIELDS: &'static [&'static str] = &[$(stringify!($name)),*];

            /// Parse and validate the `config` object of a save.
            pub fn from_json(map: &Map<String, Value>) -> Result<Self, SaveError> {
                if let Some(key) = map.keys().find(|k| !Self::FIELDS.contains(&k.as_str())) {
                    return Err(SaveError::new(format!("invalid config: unknown key {key:?}")));
                }
                let cfg = Config {
                    $($name: config_fields!(@parse map, $name, $kind $([$lo, $hi])?),)*
                };
                cfg.check_relations()?;
                Ok(cfg)
            }
        }
    };
    (@parse $map:ident, $name:ident, bool) => {
        parse_bool($map, stringify!($name))?
    };
    (@parse $map:ident, $name:ident, f64 $([$lo:expr, $hi:expr])?) => {
        parse_f64($map, stringify!($name), config_fields!(@bounds $([$lo, $hi])?))?
    };
    (@parse $map:ident, $name:ident, i64 $([$lo:expr, $hi:expr])?) => {
        parse_i64($map, stringify!($name), config_fields!(@bounds $([$lo, $hi])?))?
    };
    (@bounds) => { (0.0, INF) };
    (@bounds [$lo:expr, $hi:expr]) => { ($lo as f64, $hi as f64) };
}

config_fields! {
    // world
    width: i64 [2, 10_000],
    height: i64 [2, 10_000],
    initial_cells: i64,
    initial_energy: f64,
    // light
    light_max: f64,
    light_depth: f64 [1e-6, INF],
    shade: f64 [0, 1],
    day_length: i64 [1, 1_000_000_000],
    day_amplitude: f64 [0, 1],
    year_length: i64 [1, 1_000_000_000],
    season_amplitude: f64 [0, 1],
    // organic matter
    organic_init: f64,
    organic_diffusion: f64 [0, 1],
    organic_sink: f64 [0, 1],
    organic_decay: f64 [0, 1],
    decomp_fraction: f64 [0, 1],
    // metabolism
    base_cost: f64,
    pred_upkeep: f64,
    move_upkeep: f64,
    move_cost: f64,
    spec_exp: f64,
    // feeding
    photo_gain: f64,
    sapro_rate: f64,
    sapro_eff: f64 [0, 1],
    pred_eff: f64 [0, 1],
    chemo_gain: f64,
    // terrain (F2)
    rock_fraction: f64 [0, 0.9],
    vent_count: i64 [0, 100],
    vent_strength: f64 [0, 1e6],
    vent_radius: f64 [1e-6, INF],
    // sensing (F3)
    sensing: bool,
    sense_noise: f64 [0, 10],
    sense_upkeep: f64 [0, 10],
    // open genome (F4)
    open_genome: bool,
    rules_neutral: bool,
    rule_dup_rate: f64 [0, 1],
    rule_del_rate: f64 [0, 1],
    rule_new_rate: f64 [0, 1],
    rule_upkeep: f64 [0, 10],
    max_rules: i64 [0, 64],
    rule_div_shift: f64 [0, 1],
    // two parents (F5a)
    sex: bool,
    sex_neutral: bool,
    mate_radius: i64 [1, 5],
    mate_distance: f64 [0, 10],
    sex_cost: f64 [0, 10],
    // plasticity (F5b)
    plasticity: bool,
    plastic_neutral: bool,
    plastic_rate: f64 [0, 1],
    plastic_upkeep: f64 [0, 10],
    // horizontal gene transfer (F5c)
    hgt: bool,
    hgt_neutral: bool,
    hgt_rate: f64 [0, 1],
    hgt_upkeep: f64 [0, 10],
    // prey defence (F5e)
    defence: bool,
    defence_neutral: bool,
    defence_strength: f64 [0, 0.95],
    defence_upkeep: f64 [0, 10],
    // perception radius (ADR-0014): parsed and bounded, but `sense_range` on is refused (not ported)
    sense_range: bool,
    sense_range_neutral: bool,
    sense_radius_max: i64 [1, 5],
    sense_range_upkeep: f64 [0, 10],
    // reproduction
    body_cost: f64,
    div_min: f64,
    div_max: f64,
    max_age: i64 [1, 1_000_000_000],
    max_bonds: i64 [0, 8],
    // mutation
    mut_min: f64 [0, 1],
    mut_max: f64 [0, 1],
    // immigration
    immigration_rate: f64 [0, 100],
    // observation (never read by the dynamics)
    species_threshold: f64 [1e-9, INF],
    novelty_activity: i64 [1, 1_000_000_000_000_i64],
    species_prune_peak: i64,
    // safety
    reseed_on_extinction: bool,
}

impl Config {
    /// The cross-field checks at the end of `Config.validate()`.
    fn check_relations(&self) -> Result<(), SaveError> {
        let tiles = self.width * self.height; // both <= 10_000: no overflow
        if tiles > MAX_WORLD_TILES {
            return Err(SaveError::new(format!(
                "invalid config: world size {}x{} exceeds {MAX_WORLD_TILES} tiles",
                self.width, self.height
            )));
        }
        if self.initial_cells > tiles {
            return Err(SaveError::new(
                "invalid config: initial_cells exceeds the number of tiles",
            ));
        }
        if self.div_min > self.div_max || self.mut_min > self.mut_max {
            return Err(SaveError::new(
                "invalid config: div_min/mut_min must not exceed div_max/mut_max",
            ));
        }
        // ADR-0014: the evolvable perception radius is an experiment, ported only if it is validated.
        // Refused here, so neither a save nor `ws_world_create` can run a world the kernel would get wrong.
        if self.sense_range {
            return Err(SaveError::new(
                "invalid config: sense_range is not supported by the kernel yet (ADR-0014)",
            ));
        }
        Ok(())
    }

    /// Grid width as an index type (validated to `2..=10_000`).
    pub fn w(&self) -> usize {
        self.width as usize
    }

    /// Grid height as an index type (validated to `2..=10_000`).
    pub fn h(&self) -> usize {
        self.height as usize
    }
}

fn field<'a>(map: &'a Map<String, Value>, name: &str) -> Result<&'a Value, SaveError> {
    map.get(name)
        .ok_or_else(|| SaveError::new(format!("invalid config: missing key {name:?}")))
}

fn out_of_bounds(name: &str, v: impl std::fmt::Display, (lo, hi): (f64, f64)) -> SaveError {
    SaveError::new(format!(
        "invalid config: {name} = {v} is outside [{lo}, {hi}]"
    ))
}

fn wrong_type(name: &str, kind: &str, v: &Value) -> SaveError {
    SaveError::new(format!(
        "invalid config: {name} must be {kind}, got {}",
        json_type(v)
    ))
}

/// A float field: Python converts an int to float, rejects bools and everything else.
fn parse_f64(map: &Map<String, Value>, name: &str, bounds: (f64, f64)) -> Result<f64, SaveError> {
    let v = field(map, name)?;
    let x = match v {
        Value::Number(n) => n.as_f64().ok_or_else(|| wrong_type(name, "float", v))?,
        _ => return Err(wrong_type(name, "float", v)),
    };
    if !(x.is_finite() && bounds.0 <= x && x <= bounds.1) {
        return Err(out_of_bounds(name, x, bounds));
    }
    Ok(x)
}

/// An int field: a JSON integer (a float such as `3.0` is rejected, as in Python).
fn parse_i64(map: &Map<String, Value>, name: &str, bounds: (f64, f64)) -> Result<i64, SaveError> {
    let v = field(map, name)?;
    let x = match v {
        Value::Number(n) if !n.is_f64() => {
            n.as_i64().ok_or_else(|| out_of_bounds(name, n, bounds))?
        }
        _ => return Err(wrong_type(name, "int", v)),
    };
    if !(bounds.0 <= x as f64 && x as f64 <= bounds.1) {
        return Err(out_of_bounds(name, x, bounds));
    }
    Ok(x)
}

fn parse_bool(map: &Map<String, Value>, name: &str) -> Result<bool, SaveError> {
    match field(map, name)? {
        Value::Bool(b) => Ok(*b),
        v => Err(wrong_type(name, "bool", v)),
    }
}

/// Python-style type name for error messages.
pub(crate) fn json_type(v: &Value) -> &'static str {
    match v {
        Value::Null => "NoneType",
        Value::Bool(_) => "bool",
        Value::Number(n) if n.is_f64() => "float",
        Value::Number(_) => "int",
        Value::String(_) => "str",
        Value::Array(_) => "list",
        Value::Object(_) => "dict",
    }
}
