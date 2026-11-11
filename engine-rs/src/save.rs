//! Load a WorldSim save (`worldsim/persistence.py`, ADR-0002) into a [`World`].
//!
//! Saves are untrusted input (they may come from other players; later the kernel is called from
//! Unity): every malformed or hostile content returns a [`SaveError`], never a panic, and memory
//! stays proportional to the real data. The JSON is therefore deserialized straight into typed,
//! **capped** structures (no generic JSON tree, which costs ~30 bytes per value): every list has
//! a maximum length, refused as soon as it is exceeded, matrices share a budget of
//! [`MAX_WORLD_TILES`] elements, and ignored parts (the species tracker, species ids, unknown
//! top-level keys) are skipped without being stored.
//!
//! The checks mirror `persistence.py` (`world_from_dict`) and `Config.validate()`, with
//! deliberate differences:
//! - **stricter** where Python accepts a value its own engine never writes or could not continue
//!   from: ids, ages, lineages and the step/id/event counters must be integers in `0..=2^62`
//!   (headroom against overflow; they are hashed as `u64`), and `next_id` must not be below a
//!   cell id; rock tiles must be the integers 0/1; bonds must be symmetric, at most 8 per cell
//!   (bonded cells are neighbours), with no duplicates or self-bonds; every config key must be
//!   present (Python would fill in its defaults); the seed must be None, an int or a string; the
//!   RNG state version must be the integer 3 and its words must fit in 32 bits (CPython on Linux
//!   would truncate larger ones); `rng.gauss_next` must be a finite number or None; duplicate
//!   keys in the save object are refused;
//! - **unsupported** (until milestone M5 ports them): saves with `sensing`, `open_genome`, `sex`,
//!   `plasticity` or `hgt` on are refused; `defence` is ported (M5);
//! - **one known hash mismatch**: a JSON integer `-0` in a float slot (genes, `sex_p`, `armor_p`) becomes
//!   `-0.0` here and `0` in Python, so the two state hashes differ for that cell (the dynamics do not).
//!   Python never writes `-0`; serde_json drops the distinction before any check could see it;
//! - **looser, on purpose**: the species tracker and the per-cell species ids are not validated
//!   (only skipped). They are observer state that never affects the dynamics (ADR-0003) and the
//!   kernel never reads them.

use crate::config::{Config, MAX_WORLD_TILES};
use crate::rng::{PyRandom, MT_N};
use crate::world::{Cell, CellRef, Counters, Terrain, World, EMPTY};
use crate::{SaveError, N_GENES, SAVE_VERSION};
use flate2::read::MultiGzDecoder;
use serde::de::{self, DeserializeSeed, Deserializer, IgnoredAny, MapAccess, SeqAccess, Visitor};
use serde::Deserialize;
use serde_json::{Map, Number, Value};
use std::collections::HashMap;
use std::fmt;
use std::io::Read;
use std::marker::PhantomData;
use std::path::Path;

/// `persistence.FORMAT`.
pub const FORMAT: &str = "worldsim-save";

/// `persistence.MAX_SAVE_BYTES`: decompressed size cap, a guard against gzip bombs.
pub const MAX_SAVE_BYTES: u64 = 512 * 1024 * 1024;

/// `persistence.CELL_ROW_LEN`: fields per cell row.
pub const CELL_ROW_LEN: usize = 15;

/// Largest step, id, age, lineage or event counter accepted from a save: far above anything a
/// run reaches, and far enough below `u64::MAX` that no later increment can overflow.
pub const MAX_COUNT: u64 = 1 << 62;

/// Most bonds a cell can have: bonded cells are neighbours (they never move), so at most 8.
pub const MAX_BONDS: usize = 8;

const MAX_SIDE: usize = 10_000; // `_BOUNDS` of width and height
const MAX_CELLS: usize = MAX_WORLD_TILES as usize; // at most one cell per tile
const MAX_CONFIG_KEYS: usize = 256;

/// Load a gzip JSON save from disk (streamed through the decompressor, never read whole).
pub fn load_world(path: impl AsRef<Path>) -> Result<World, SaveError> {
    let path = path.as_ref();
    let file = std::fs::File::open(path)
        .map_err(|e| SaveError::new(format!("cannot read {}: {e}", path.display())))?;
    decompress(std::io::BufReader::new(file), MAX_SAVE_BYTES).and_then(|d| world_from_json(&d))
}

/// Decompress (at most `max_bytes`) and load a save.
pub fn world_from_gzip(compressed: &[u8], max_bytes: u64) -> Result<World, SaveError> {
    world_from_json(&decompress(compressed, max_bytes)?)
}

fn decompress(compressed: impl Read, max_bytes: u64) -> Result<Vec<u8>, SaveError> {
    let mut data = Vec::new();
    MultiGzDecoder::new(compressed)
        .take(max_bytes.saturating_add(1))
        .read_to_end(&mut data)
        .map_err(|e| SaveError::new(crate::bounded(format_args!("not a valid save file: {e}"))))?;
    if data.len() as u64 > max_bytes {
        return Err(SaveError::new(format!(
            "save decompresses to more than {max_bytes} bytes"
        )));
    }
    Ok(data)
}

/// Load a save from its (decompressed) JSON text.
pub fn world_from_json(json: &[u8]) -> Result<World, SaveError> {
    let raw: RawSave = serde_json::from_slice(json)
        .map_err(|e| SaveError::new(crate::bounded(format_args!("not a valid save file: {e}"))))?;
    build_world(raw)
}

// ------------------------------------------------------------------ typed, capped JSON

/// The save object. Unknown top-level keys are skipped (as in Python), not stored.
#[derive(Deserialize)]
struct RawSave {
    format: String,
    version: u64,
    config: ConfigMap,
    #[allow(dead_code)] // checked by its Deserialize impl, otherwise unused
    seed: Seed,
    step_count: u64,
    next_id: u64,
    counters: RawCounters,
    rng: RawRng,
    organic: Matrix<f64>,
    terrain: Option<RawTerrain>, // Python: `d.get("terrain")`
    cells: Capped<RawCell, MAX_CELLS>,
    #[allow(dead_code)] // observer state: required, skipped
    tracker: IgnoredAny,
}

/// Other counters (later F-phases may add some) are skipped, as Python whitelists these.
#[derive(Deserialize)]
struct RawCounters {
    births: u64,
    deaths: u64,
    kills: u64,
    extinctions: u64,
    sex_births: u64,
    hgt_events: u64,
    hgt_foreign: u64,
    defended: u64,
}

#[derive(Deserialize)]
struct RawRng {
    version: u64,
    internal: Capped<u64, { MT_N + 1 }>,
    #[serde(deserialize_with = "Option::deserialize")] // required key, may be null
    gauss_next: Option<f64>,
}

#[derive(Deserialize)]
struct RawTerrain {
    rock: Matrix<Bit>,
    chem: Matrix<f64>,
    sun: Capped<f64, MAX_SIDE>,
}

/// `[id, x, y, energy, age, genes, lineage, species, bonds, rules, sex_p, plast_p, diet, hgt_p, armor_p]`.
/// Rules and diet must be empty with their flags off (checked by the cap of 0).
#[derive(Deserialize)]
#[allow(dead_code)] // rules and diet (fields 9, 12) are only length-checked
struct RawCell(
    u64,
    u64,
    u64,
    f64,
    u64,
    [f64; N_GENES],
    u64,
    IgnoredAny,
    Capped<u64, MAX_BONDS>,
    Capped<IgnoredAny, 0>,
    f64,
    f64,
    Capped<IgnoredAny, 0>,
    f64,
    f64,
);

/// A JSON list of at most `N` elements, refused as soon as it grows past `N`.
struct Capped<T, const N: usize>(Vec<T>);

impl<'de, T: Deserialize<'de>, const N: usize> Deserialize<'de> for Capped<T, N> {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V<T, const N: usize>(PhantomData<T>);
        impl<'de, T: Deserialize<'de>, const N: usize> Visitor<'de> for V<T, N> {
            type Value = Capped<T, N>;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                write!(f, "a list of at most {N} elements")
            }
            fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<Self::Value, A::Error> {
                let mut out = Vec::new();
                while let Some(x) = seq.next_element()? {
                    if out.len() == N {
                        return Err(de::Error::custom(format!("list longer than {N} elements")));
                    }
                    out.push(x);
                }
                Ok(Capped(out))
            }
        }
        d.deserialize_seq(V(PhantomData))
    }
}

/// A list of rows (`(H, W)` map) of at most [`MAX_SIDE`] x [`MAX_SIDE`] and
/// [`MAX_WORLD_TILES`] elements in total; the exact shape is checked against the config later.
struct Matrix<T>(Vec<Vec<T>>);

impl<'de, T: Deserialize<'de>> Deserialize<'de> for Matrix<T> {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct Rows<T>(PhantomData<T>);
        impl<'de, T: Deserialize<'de>> Visitor<'de> for Rows<T> {
            type Value = Matrix<T>;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                write!(f, "a list of rows")
            }
            fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<Self::Value, A::Error> {
                let mut budget = MAX_CELLS;
                let mut rows = Vec::new();
                while let Some(row) = seq.next_element_seed(RowSeed::<T> {
                    budget: &mut budget,
                    item: PhantomData,
                })? {
                    if rows.len() == MAX_SIDE {
                        return Err(de::Error::custom("map has too many rows"));
                    }
                    rows.push(row);
                }
                Ok(Matrix(rows))
            }
        }
        d.deserialize_seq(Rows(PhantomData))
    }
}

/// One matrix row, drawing its elements from the matrix's shared budget.
struct RowSeed<'b, T> {
    budget: &'b mut usize,
    item: PhantomData<T>,
}

impl<'de, T: Deserialize<'de>> DeserializeSeed<'de> for RowSeed<'_, T> {
    type Value = Vec<T>;
    fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<T>, D::Error> {
        d.deserialize_seq(self)
    }
}

impl<'de, T: Deserialize<'de>> Visitor<'de> for RowSeed<'_, T> {
    type Value = Vec<T>;
    fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "a row of at most {MAX_SIDE} numbers")
    }
    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<Vec<T>, A::Error> {
        let mut row = Vec::new();
        while let Some(x) = seq.next_element()? {
            if row.len() == MAX_SIDE || *self.budget == 0 {
                return Err(de::Error::custom("map is larger than any valid world"));
            }
            *self.budget -= 1;
            row.push(x);
        }
        Ok(row)
    }
}

/// A rock tile: the integer 0 or 1.
struct Bit(bool);

impl<'de> Deserialize<'de> for Bit {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl Visitor<'_> for V {
            type Value = Bit;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                write!(f, "terrain rock map must contain only 0 and 1")
            }
            fn visit_u64<E: de::Error>(self, v: u64) -> Result<Bit, E> {
                match v {
                    0 => Ok(Bit(false)),
                    1 => Ok(Bit(true)),
                    _ => Err(E::custom("terrain rock map must contain only 0 and 1")),
                }
            }
        }
        d.deserialize_u64(V)
    }
}

/// The `config` object: at most [`MAX_CONFIG_KEYS`] keys, scalar values only (bool, int,
/// float), kept as JSON values so `Config::from_json` can tell ints from floats like Python.
struct ConfigMap(Map<String, Value>);

impl<'de> Deserialize<'de> for ConfigMap {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = ConfigMap;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                write!(f, "a config dict")
            }
            fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<ConfigMap, A::Error> {
                let mut out = Map::new();
                while let Some((k, Scalar(v))) = map.next_entry::<String, Scalar>()? {
                    if out.len() == MAX_CONFIG_KEYS {
                        return Err(de::Error::custom("config has too many keys"));
                    }
                    out.insert(k, v);
                }
                Ok(ConfigMap(out))
            }
        }
        d.deserialize_map(V)
    }
}

/// A bool or number; anything else is refused without being stored.
struct Scalar(Value);

impl<'de> Deserialize<'de> for Scalar {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl Visitor<'_> for V {
            type Value = Scalar;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                write!(f, "a config value (bool, int or float)")
            }
            fn visit_bool<E: de::Error>(self, v: bool) -> Result<Scalar, E> {
                Ok(Scalar(Value::Bool(v)))
            }
            fn visit_i64<E: de::Error>(self, v: i64) -> Result<Scalar, E> {
                Ok(Scalar(Value::Number(v.into())))
            }
            fn visit_u64<E: de::Error>(self, v: u64) -> Result<Scalar, E> {
                Ok(Scalar(Value::Number(v.into())))
            }
            fn visit_f64<E: de::Error>(self, v: f64) -> Result<Scalar, E> {
                Number::from_f64(v)
                    .map(|n| Scalar(Value::Number(n)))
                    .ok_or_else(|| E::custom("config value is not finite"))
            }
        }
        d.deserialize_any(V)
    }
}

/// `random.Random(seed)` accepts None, an int or a string; only the restored state is used.
struct Seed;

impl<'de> Deserialize<'de> for Seed {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl Visitor<'_> for V {
            type Value = Seed;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                write!(f, "a seed (None, int or str)")
            }
            fn visit_unit<E: de::Error>(self) -> Result<Seed, E> {
                Ok(Seed)
            }
            fn visit_i64<E: de::Error>(self, _: i64) -> Result<Seed, E> {
                Ok(Seed)
            }
            fn visit_u64<E: de::Error>(self, _: u64) -> Result<Seed, E> {
                Ok(Seed)
            }
            fn visit_str<E: de::Error>(self, _: &str) -> Result<Seed, E> {
                Ok(Seed)
            }
        }
        d.deserialize_any(V)
    }
}

// ------------------------------------------------------------------ validation

fn err(message: impl Into<String>) -> SaveError {
    SaveError::new(message)
}

fn count(v: u64, what: &str) -> Result<u64, SaveError> {
    if v > MAX_COUNT {
        return Err(err(format!("malformed save: {what} {v} exceeds 2^62")));
    }
    Ok(v)
}

fn build_world(raw: RawSave) -> Result<World, SaveError> {
    if raw.format != FORMAT {
        return Err(err("not a WorldSim save file"));
    }
    if raw.version != u64::from(SAVE_VERSION) {
        return Err(err(format!(
            "unsupported save version {} (expected {SAVE_VERSION})",
            raw.version
        )));
    }
    let cfg = Config::from_json(&raw.config.0)?;
    for (flag, on) in [
        ("sensing", cfg.sensing),
        ("open_genome", cfg.open_genome),
        ("sex", cfg.sex),
        ("plasticity", cfg.plasticity),
        ("hgt", cfg.hgt),
    ] {
        if on {
            return Err(err(format!(
                "unsupported save: {flag} is on (this kernel does not run it yet, M5)"
            )));
        }
    }
    let (w, h) = (cfg.w(), cfg.h());
    let terrain = match raw.terrain {
        None => Terrain::flat(w, h),
        Some(t) => build_terrain(t, w, h)?,
    };
    let c = &raw.counters;
    let counters = Counters {
        births: count(c.births, "counter births")?,
        deaths: count(c.deaths, "counter deaths")?,
        kills: count(c.kills, "counter kills")?,
        extinctions: count(c.extinctions, "counter extinctions")?,
        sex_births: count(c.sex_births, "counter sex_births")?,
        defended: count(c.defended, "counter defended")?,
    };
    // Observer-only counters (F5c): validated as Python does, never read by the kernel.
    if count(c.hgt_foreign, "counter hgt_foreign")? > count(c.hgt_events, "counter hgt_events")? {
        return Err(err("invalid counters: hgt_foreign exceeds hgt_events"));
    }
    let rng = build_rng(&raw.rng)?;
    let organic = matrix_values(raw.organic, w, h, "organic field")?;

    let mut world = World::from_parts(cfg, terrain, rng, organic);
    world.step_count = count(raw.step_count, "step_count")?;
    world.next_id = count(raw.next_id, "next_id")?;
    world.counters = counters;
    load_cells(&mut world, raw.cells.0)?;
    // `persistence.py` recomputes the light at load (`now = step_count`); it is not hashed.
    world.update_light(world.step_count);
    Ok(world)
}

/// `Random.setstate((3, internal, gauss_next))`.
fn build_rng(r: &RawRng) -> Result<PyRandom, SaveError> {
    if r.version != 3 {
        return Err(err("malformed save: RNG state version must be 3"));
    }
    let words = r
        .internal
        .0
        .iter()
        .map(|&x| {
            u32::try_from(x).map_err(|_| {
                err(format!(
                    "malformed save: RNG state word {x} exceeds 32 bits"
                ))
            })
        })
        .collect::<Result<Vec<u32>, _>>()?;
    if r.gauss_next.is_some_and(|z| !z.is_finite()) {
        return Err(err("malformed save: rng.gauss_next must be finite"));
    }
    PyRandom::from_state(&words, r.gauss_next).map_err(|e| err(format!("malformed save: {e}")))
}

/// Flatten an `(h, w)` map row-major, checking its shape.
fn flatten<T>(m: Matrix<T>, w: usize, h: usize, what: &str) -> Result<Vec<T>, SaveError> {
    if m.0.len() != h || m.0.iter().any(|row| row.len() != w) {
        return Err(err(format!("{what} does not match the {w}x{h} world")));
    }
    Ok(m.0.into_iter().flatten().collect())
}

/// An `(h, w)` map of finite, non-negative numbers.
fn matrix_values(m: Matrix<f64>, w: usize, h: usize, what: &str) -> Result<Vec<f64>, SaveError> {
    let v = flatten(m, w, h, what)?;
    if !v.iter().all(|&x| x.is_finite() && x >= 0.0) {
        return Err(err(format!("{what} must be finite and non-negative")));
    }
    Ok(v)
}

/// `_terrain_from_dict`: rock (0/1), chem `(H, W)` and sun `(W,)`.
fn build_terrain(t: RawTerrain, w: usize, h: usize) -> Result<Terrain, SaveError> {
    let rock = flatten(t.rock, w, h, "terrain rock map")?;
    let chem = matrix_values(t.chem, w, h, "terrain chem map")?;
    let sun = matrix_values(Matrix(vec![t.sun.0]), w, 1, "terrain sun map")?;
    Ok(Terrain {
        rock: rock.into_iter().map(|b| b.0).collect(),
        chem,
        sun,
    })
}

/// Place the cells in list order, then restore the bonds in insertion order.
fn load_cells(world: &mut World, rows: Vec<RawCell>) -> Result<(), SaveError> {
    let (w, h) = (world.width, world.height);
    let mut by_id: HashMap<u64, CellRef> = HashMap::new();
    let mut bond_ids: Vec<Vec<u64>> = Vec::with_capacity(rows.len().min(w * h));
    for row in rows {
        let RawCell(
            id,
            x,
            y,
            energy,
            age,
            genes,
            lineage,
            _,
            bonds,
            _,
            sex_p,
            plast_p,
            _,
            hgt_p,
            armor_p,
        ) = row;
        if !(x < w as u64 && y < h as u64) {
            return Err(err(format!("cell #{id} outside the grid at ({x}, {y})")));
        }
        let (x, y) = (x as usize, y as usize);
        let tile = y * w + x;
        if world.grid[tile] != EMPTY || world.terrain.rock[tile] {
            return Err(err(format!(
                "cell #{id} on an occupied or rock tile at ({x}, {y})"
            )));
        }
        let genes_ok = genes
            .iter()
            .all(|g| g.is_finite() && (0.0..=1.0).contains(g));
        if !energy.is_finite() || !genes_ok || by_id.contains_key(&id) {
            return Err(err(format!("invalid cell #{id}")));
        }
        if id > world.next_id {
            return Err(err(format!(
                "cell #{id} is above next_id {}",
                world.next_id
            )));
        }
        // With sex, plasticity and hgt off (checked above) Python accepts only zero propensities.
        if !(sex_p.is_finite() && sex_p == 0.0) {
            return Err(err(format!("cell #{id} has an invalid sex_p")));
        }
        if !(plast_p.is_finite() && plast_p == 0.0) {
            return Err(err(format!("cell #{id} has an invalid plast_p")));
        }
        if !(hgt_p.is_finite() && hgt_p == 0.0) {
            return Err(err(format!("cell #{id} has an invalid hgt_p")));
        }
        // `persistence.py`: finite, in [0, 1], and zero (or -0.0) unless defence is on.
        let armor_ok = armor_p.is_finite()
            && (0.0..=1.0).contains(&armor_p)
            && (world.cfg.defence || armor_p == 0.0);
        if !armor_ok {
            return Err(err(format!("cell #{id} has an invalid armor_p")));
        }
        let r = world.slab.len() as CellRef;
        let mut cell = Cell::new(
            id,
            x,
            y,
            energy,
            genes,
            count(lineage, "cell lineage")?,
            armor_p, // keeps the sign of a -0.0 (it is hashed by bits)
            &world.cfg,
        );
        cell.age = count(age, "cell age")?;
        cell.sex_p = sex_p; // keeps the sign of a -0.0 (it is hashed by bits)
        world.slab.push(cell);
        world.order.push(r);
        world.grid[tile] = r;
        by_id.insert(id, r);
        bond_ids.push(bonds.0);
    }

    for (r, ids) in bond_ids.into_iter().enumerate() {
        let id = world.slab[r].id;
        let mut bonds = Vec::with_capacity(ids.len());
        for bid in ids {
            let b = *by_id
                .get(&bid)
                .ok_or_else(|| err(format!("cell #{id} bonded to missing cell #{bid}")))?;
            if b as usize == r || bonds.contains(&b) {
                return Err(err(format!("cell #{id} has a self or duplicate bond")));
            }
            bonds.push(b);
        }
        world.slab[r].bonds = bonds;
    }
    for r in 0..world.slab.len() {
        for &b in &world.slab[r].bonds {
            if !world.slab[b as usize].bonds.contains(&(r as CellRef)) {
                return Err(err(format!(
                    "bond between cells #{} and #{} is not symmetric",
                    world.slab[r].id, world.slab[b as usize].id
                )));
            }
        }
    }
    Ok(())
}
