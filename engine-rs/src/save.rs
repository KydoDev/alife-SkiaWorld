//! Load a WorldSim save (`worldsim/persistence.py`, ADR-0002) into a [`World`].
//!
//! Saves are untrusted input (they may come from other players): every malformed or hostile
//! content returns a [`SaveError`], never a panic. The checks mirror `persistence.py`
//! (`world_from_dict`, `Config.validate`), with three deliberate differences:
//! - **stricter** where Python accepts a value its own engine would never write or could not
//!   continue from: ids, ages, lineages, step and id counters must be unsigned 64-bit integers
//!   (they are hashed as `u64`); rock tiles must be the integers 0/1; bonds must be symmetric,
//!   without duplicates or self-bonds; every config key must be present;
//! - **unsupported** (until milestone M5): saves with `sensing`, `open_genome`, `sex` or
//!   `plasticity` on are refused, since this kernel only runs the default flags;
//! - **ignored**: the species tracker and the per-cell species ids, which are observer state
//!   and never affect the dynamics (ADR-0003). They are not parsed beyond JSON.

use crate::config::{json_type, Config};
use crate::rng::{PyRandom, MT_N};
use crate::world::{Cell, CellRef, Counters, Terrain, World, EMPTY};
use crate::{SaveError, N_GENES, SAVE_VERSION};
use flate2::read::MultiGzDecoder;
use serde_json::{Map, Value};
use std::collections::HashMap;
use std::io::Read;
use std::path::Path;

/// `persistence.FORMAT`.
pub const FORMAT: &str = "worldsim-save";

/// `persistence.MAX_SAVE_BYTES`: decompressed size cap, a guard against gzip bombs.
pub const MAX_SAVE_BYTES: u64 = 512 * 1024 * 1024;

/// `persistence.CELL_ROW_LEN`: fields per cell row.
pub const CELL_ROW_LEN: usize = 13;

/// Load a gzip JSON save from disk.
pub fn load_world(path: impl AsRef<Path>) -> Result<World, SaveError> {
    let path = path.as_ref();
    let bytes = std::fs::read(path)
        .map_err(|e| SaveError::new(format!("cannot read {}: {e}", path.display())))?;
    world_from_gzip(&bytes, MAX_SAVE_BYTES)
}

/// Decompress (at most `max_bytes`) and load a save.
pub fn world_from_gzip(compressed: &[u8], max_bytes: u64) -> Result<World, SaveError> {
    let mut data = Vec::new();
    MultiGzDecoder::new(compressed)
        .take(max_bytes.saturating_add(1))
        .read_to_end(&mut data)
        .map_err(|e| SaveError::new(format!("not a valid save file: {e}")))?;
    if data.len() as u64 > max_bytes {
        return Err(SaveError::new(format!(
            "save decompresses to more than {max_bytes} bytes"
        )));
    }
    world_from_json(&data)
}

/// Load a save from its (decompressed) JSON text.
pub fn world_from_json(json: &[u8]) -> Result<World, SaveError> {
    let value: Value = serde_json::from_slice(json)
        .map_err(|e| SaveError::new(format!("not a valid save file: {e}")))?;
    world_from_value(&value)
}

/// Rebuild a world from a parsed save.
pub fn world_from_value(d: &Value) -> Result<World, SaveError> {
    let d = match d {
        Value::Object(m) if m.get("format").and_then(Value::as_str) == Some(FORMAT) => m,
        _ => return Err(SaveError::new("not a WorldSim save file")),
    };
    let version = d.get("version");
    if version.and_then(Value::as_u64) != Some(u64::from(SAVE_VERSION)) {
        return Err(SaveError::new(format!(
            "unsupported save version {} (expected {SAVE_VERSION})",
            version.map_or("None".to_string(), Value::to_string)
        )));
    }

    let cfg = Config::from_json(object(get(d, "config")?, "config")?)?;
    for (flag, on) in [
        ("sensing", cfg.sensing),
        ("open_genome", cfg.open_genome),
        ("sex", cfg.sex),
        ("plasticity", cfg.plasticity),
    ] {
        if on {
            return Err(SaveError::new(format!(
                "unsupported save: {flag} is on (this kernel runs the default flags only, until M5)"
            )));
        }
    }
    let (w, h) = (cfg.w(), cfg.h());
    let terrain = parse_terrain(get(d, "terrain")?, w, h)?;
    check_seed(get(d, "seed")?)?;
    get(d, "tracker")?; // observer state: required, not used (see the module docs)

    let step_count = uint(get(d, "step_count")?, "step_count")?;
    let next_id = uint(get(d, "next_id")?, "next_id")?;
    let counters = parse_counters(object(get(d, "counters")?, "counters")?)?;
    let rng = parse_rng(object(get(d, "rng")?, "rng")?)?;
    let organic = parse_organic(get(d, "organic")?, w, h)?;

    let mut world = World {
        cfg,
        width: w,
        height: h,
        step_count,
        next_id,
        counters,
        rng,
        organic,
        terrain,
        slab: Vec::new(),
        order: Vec::new(),
        grid: vec![EMPTY; w * h],
    };
    load_cells(&mut world, array(get(d, "cells")?, "cells")?)?;
    Ok(world)
}

fn get<'a>(map: &'a Map<String, Value>, key: &str) -> Result<&'a Value, SaveError> {
    map.get(key)
        .ok_or_else(|| SaveError::new(format!("malformed save: missing key {key:?}")))
}

fn object<'a>(v: &'a Value, what: &str) -> Result<&'a Map<String, Value>, SaveError> {
    v.as_object().ok_or_else(|| {
        SaveError::new(format!(
            "malformed save: {what} must be a dict, got {}",
            json_type(v)
        ))
    })
}

fn array<'a>(v: &'a Value, what: &str) -> Result<&'a [Value], SaveError> {
    v.as_array().map(Vec::as_slice).ok_or_else(|| {
        SaveError::new(format!(
            "malformed save: {what} must be a list, got {}",
            json_type(v)
        ))
    })
}

/// A non-negative integer that fits in `u64` (bools and floats are not integers here).
fn uint(v: &Value, what: &str) -> Result<u64, SaveError> {
    match v {
        Value::Number(n) if !n.is_f64() => n.as_u64(),
        _ => None,
    }
    .ok_or_else(|| {
        SaveError::new(format!(
            "malformed save: {what} must be a non-negative integer, got {v}"
        ))
    })
}

/// An int or float (Python's `_finite` also rejects bools), as `f64`. JSON cannot hold NaN or
/// infinities, but a huge integer would overflow to infinity, so finiteness is still checked.
fn finite(v: &Value) -> Option<f64> {
    v.as_f64().filter(|x| x.is_finite())
}

fn check_seed(v: &Value) -> Result<(), SaveError> {
    // `random.Random(seed)` accepts None, int, float-free str/bytes; only the restored state is used.
    match v {
        Value::Null | Value::String(_) => Ok(()),
        Value::Number(n) if !n.is_f64() => Ok(()),
        _ => Err(SaveError::new(format!(
            "malformed save: invalid seed of type {}",
            json_type(v)
        ))),
    }
}

fn parse_counters(m: &Map<String, Value>) -> Result<Counters, SaveError> {
    let counter = |k: &str| {
        m.get(k)
            .and_then(|v| match v {
                Value::Number(n) if !n.is_f64() => n.as_u64(),
                _ => None,
            })
            .ok_or_else(|| SaveError::new(format!("invalid counter {k:?}")))
    };
    Ok(Counters {
        births: counter("births")?,
        deaths: counter("deaths")?,
        kills: counter("kills")?,
        extinctions: counter("extinctions")?,
        sex_births: counter("sex_births")?,
    })
}

/// `Random.setstate((version, internal, gauss_next))` with version 3.
fn parse_rng(m: &Map<String, Value>) -> Result<PyRandom, SaveError> {
    if get(m, "version")?.as_u64() != Some(3) {
        return Err(SaveError::new(
            "malformed save: RNG state version must be 3",
        ));
    }
    let internal = array(get(m, "internal")?, "rng.internal")?;
    if internal.len() != MT_N + 1 {
        return Err(SaveError::new(format!(
            "malformed save: RNG state has {} words, expected {}",
            internal.len(),
            MT_N + 1
        )));
    }
    let words = internal
        .iter()
        .map(|v| {
            uint(v, "an RNG state word").and_then(|x| {
                u32::try_from(x).map_err(|_| {
                    SaveError::new(format!(
                        "malformed save: RNG state word {x} exceeds 32 bits"
                    ))
                })
            })
        })
        .collect::<Result<Vec<u32>, _>>()?;
    let gauss_next = match get(m, "gauss_next")? {
        Value::Null => None,
        v => Some(finite(v).ok_or_else(|| {
            SaveError::new("malformed save: rng.gauss_next must be None or a finite number")
        })?),
    };
    PyRandom::from_state(&words, gauss_next)
        .map_err(|e| SaveError::new(format!("malformed save: {e}")))
}

/// A `(rows, cols)` matrix of finite, non-negative numbers, row-major.
fn matrix(v: &Value, rows: usize, cols: usize, what: &str) -> Result<Vec<f64>, SaveError> {
    let shape_err = || SaveError::new(format!("{what} does not match the {cols}x{rows} world"));
    let value_err = || SaveError::new(format!("{what} must be finite and non-negative"));
    let rows_v = v.as_array().ok_or_else(shape_err)?;
    if rows_v.len() != rows {
        return Err(shape_err());
    }
    let mut out = Vec::with_capacity(rows * cols);
    for row in rows_v {
        let row = row.as_array().ok_or_else(shape_err)?;
        if row.len() != cols {
            return Err(shape_err());
        }
        for x in row {
            match finite(x) {
                Some(x) if x >= 0.0 => out.push(x),
                _ => return Err(value_err()),
            }
        }
    }
    Ok(out)
}

fn parse_organic(v: &Value, w: usize, h: usize) -> Result<Vec<f64>, SaveError> {
    matrix(v, h, w, "organic field")
}

/// `_terrain_from_dict`: `null` = flat; else `rock` (0/1), `chem` (H, W) and `sun` (W).
fn parse_terrain(v: &Value, w: usize, h: usize) -> Result<Terrain, SaveError> {
    let m = match v {
        Value::Null => return Ok(Terrain::flat(w, h)),
        Value::Object(m) => m,
        _ => return Err(SaveError::new("invalid terrain: must be None or a dict")),
    };
    let missing = |k: &str| SaveError::new(format!("invalid terrain: missing key {k:?}"));
    let rock_v = m.get("rock").ok_or_else(|| missing("rock"))?;
    let chem_v = m.get("chem").ok_or_else(|| missing("chem"))?;
    let sun_v = m.get("sun").ok_or_else(|| missing("sun"))?;

    let shape_err = || SaveError::new(format!("terrain maps do not match the {w}x{h} world"));
    let rows = rock_v.as_array().ok_or_else(shape_err)?;
    if rows.len() != h {
        return Err(shape_err());
    }
    let mut rock = Vec::with_capacity(w * h);
    for row in rows {
        let row = row.as_array().ok_or_else(shape_err)?;
        if row.len() != w {
            return Err(shape_err());
        }
        for t in row {
            match t {
                Value::Number(n) if !n.is_f64() && n.as_u64() == Some(0) => rock.push(false),
                Value::Number(n) if !n.is_f64() && n.as_u64() == Some(1) => rock.push(true),
                _ => return Err(SaveError::new("terrain rock map must contain only 0 and 1")),
            }
        }
    }
    let chem = matrix(chem_v, h, w, "terrain chem map")?;
    let sun_row = Value::Array(vec![sun_v.clone()]);
    let sun = matrix(&sun_row, 1, w, "terrain sun map")?;
    Ok(Terrain { rock, chem, sun })
}

/// The `cells` rows: `[id, x, y, energy, age, genes, lineage, species, bonds, rules, sex_p,
/// plast_p, diet]`, placed in list order, then the bonds in insertion order.
fn load_cells(world: &mut World, rows: &[Value]) -> Result<(), SaveError> {
    let (w, h) = (world.width, world.height);
    let mut by_id: HashMap<u64, CellRef> = HashMap::with_capacity(rows.len());
    let mut bond_ids: Vec<&[Value]> = Vec::with_capacity(rows.len());
    for row in rows {
        let row = match row.as_array() {
            Some(r) if r.len() == CELL_ROW_LEN => r,
            _ => {
                return Err(SaveError::new(format!(
                    "every cell row must have {CELL_ROW_LEN} fields"
                )))
            }
        };
        let id = uint(&row[0], "cell id")?;
        let invalid = |what: &str| SaveError::new(format!("cell #{id} has an invalid {what}"));
        let (x, y) = match (uint(&row[1], "cell x"), uint(&row[2], "cell y")) {
            (Ok(x), Ok(y)) if x < w as u64 && y < h as u64 => (x as usize, y as usize),
            _ => {
                return Err(SaveError::new(format!(
                    "cell #{id} outside the grid at ({}, {})",
                    row[1], row[2]
                )))
            }
        };
        let tile = y * w + x;
        if world.grid[tile] != EMPTY || world.terrain.rock[tile] {
            return Err(SaveError::new(format!(
                "cell #{id} on an occupied or rock tile at ({x}, {y})"
            )));
        }
        let energy =
            finite(&row[3]).ok_or_else(|| SaveError::new(format!("invalid cell #{id}")))?;
        let age = uint(&row[4], "cell age")?;
        let genes_v = row[5].as_array().filter(|g| g.len() == N_GENES);
        let mut genes = [0.0; N_GENES];
        let genes_ok = genes_v.is_some_and(|gv| {
            gv.iter()
                .zip(genes.iter_mut())
                .all(|(v, g)| match finite(v) {
                    Some(x) if (0.0..=1.0).contains(&x) => {
                        *g = x;
                        true
                    }
                    _ => false,
                })
        });
        if !genes_ok || by_id.contains_key(&id) {
            return Err(SaveError::new(format!("invalid cell #{id}")));
        }
        let lineage = uint(&row[6], "cell lineage")?;
        // row[7] = species: observer state, ignored
        let bonds = row[8].as_array().ok_or_else(|| invalid("bond list"))?;
        // With open_genome, sex and plasticity off (checked above), Python accepts only an
        // empty rule list, a zero sex_p / plast_p and an empty diet.
        if !row[9].as_array().is_some_and(Vec::is_empty) {
            return Err(SaveError::new(format!("cell #{id} has invalid rule genes")));
        }
        let sex_p = match finite(&row[10]) {
            Some(v) if v == 0.0 => v, // keeps the sign of a -0.0 (it is hashed by bits)
            _ => return Err(SaveError::new(format!("cell #{id} has an invalid sex_p"))),
        };
        if finite(&row[11]) != Some(0.0) {
            return Err(SaveError::new(format!("cell #{id} has an invalid plast_p")));
        }
        if !row[12].as_array().is_some_and(Vec::is_empty) {
            return Err(SaveError::new(format!("cell #{id} has an invalid diet")));
        }

        let r = world.slab.len() as CellRef;
        world.slab.push(Cell {
            id,
            x,
            y,
            energy,
            age,
            genes,
            lineage,
            bonds: Vec::new(),
            sex_p,
            alive: true,
        });
        world.order.push(r);
        world.grid[tile] = r;
        by_id.insert(id, r);
        bond_ids.push(bonds);
    }

    for (r, ids) in bond_ids.into_iter().enumerate() {
        let id = world.slab[r].id;
        let mut bonds = Vec::with_capacity(ids.len());
        for v in ids {
            let b = uint(v, "bond id")
                .ok()
                .and_then(|bid| by_id.get(&bid).copied())
                .ok_or_else(|| SaveError::new(format!("cell #{id} bonded to missing cell #{v}")))?;
            if b as usize == r || bonds.contains(&b) {
                return Err(SaveError::new(format!(
                    "cell #{id} has a self or duplicate bond"
                )));
            }
            bonds.push(b);
        }
        world.slab[r].bonds = bonds;
    }
    for r in 0..world.slab.len() {
        for &b in &world.slab[r].bonds {
            if !world.slab[b as usize].bonds.contains(&(r as CellRef)) {
                return Err(SaveError::new(format!(
                    "bond between cells #{} and #{} is not symmetric",
                    world.slab[r].id, world.slab[b as usize].id
                )));
            }
        }
    }
    Ok(())
}
