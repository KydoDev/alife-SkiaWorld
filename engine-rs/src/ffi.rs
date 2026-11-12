//! C ABI for front-ends (G2 M4: Unity through P/Invoke).
//!
//! Only what `docs/G2_PLAN.md` allows across the boundary: loading a save, creating a world from a
//! config and a seed (ADR-0012), stepping, the five validated G1 edits (ADR-0013), and read-only views
//! (sizes and light factor, state hash, an RGB render, the tile snapshot and a cell's record: ADR-0016). No raw field writes: an edit is a domain operation that the core
//! validates before changing anything.
//!
//! Contract for every function:
//! - A world is an opaque handle from [`ws_world_load`] or [`ws_world_create`], released with
//!   [`ws_world_free`].
//! - Status codes: [`WS_OK`] (0) or a negative error; the message of the last failure on this
//!   thread is copied out by [`ws_last_error`].
//! - Pointers are checked for null and buffers for their exact length; no panic crosses the
//!   boundary (each entry point runs inside `catch_unwind`). A panic inside a step or an edit may
//!   leave the world half-updated, so the handle is then poisoned and every later call on it fails.
//!   A refused edit ([`WS_ERR_INVALID`]) changed nothing and does not poison the handle.
//! - A handle must not be used from two threads at once, nor after it is freed.

use crate::hash::state_hash;
use crate::render::{render_rgb, rgb_len};
use crate::save::{config_from_json, world_from_gzip, MAX_SAVE_BYTES};
use crate::views::{cell_record, tile_words, tiles_len, N_TRAITS};
use crate::world::{
    Intervention, World, KIND_DIG, KIND_METEORITE, KIND_NUTRIENTS, KIND_RAISE_ROCK, KIND_VENT,
};
use std::cell::RefCell;
use std::fmt;
use std::panic::{catch_unwind, AssertUnwindSafe};

// The whole boundary relies on unwinding to catch panics.
#[cfg(panic = "abort")]
compile_error!("the C ABI needs panic = unwind");

/// One counter for the whole ABI, bumped once per commit that changes it (an added entry point
/// included, ADR-0012); front-ends refuse a mismatch. 2: [`ws_world_create`]; 3:
/// [`ws_world_intervene`] and [`WS_ERR_INVALID`] (ADR-0013); 4: [`ws_world_tiles`], [`ws_world_cell`] and
/// [`WsInfo::light_factor`] (ADR-0016).
pub const WS_ABI_VERSION: u32 = 4;

pub const WS_OK: i32 = 0;
/// A null pointer or a buffer of the wrong size.
pub const WS_ERR_ARGUMENT: i32 = -1;
/// A panic was caught; the handle, if any, is now poisoned.
pub const WS_ERR_PANIC: i32 = -3;
/// The handle was poisoned by an earlier panic.
pub const WS_ERR_POISONED: i32 = -4;
/// An edit the core refused (bad kind, tile or amount); nothing changed and the handle stays usable.
/// (-2 is unused; the list is appended to, not back-filled.)
pub const WS_ERR_INVALID: i32 = -5;

/// Edit kinds of [`ws_world_intervene`]; 0 is never an action, so zeroed memory is refused.
pub const WS_EDIT_NUTRIENTS: u32 = KIND_NUTRIENTS;
pub const WS_EDIT_METEORITE: u32 = KIND_METEORITE;
pub const WS_EDIT_RAISE_ROCK: u32 = KIND_RAISE_ROCK;
pub const WS_EDIT_DIG: u32 = KIND_DIG;
pub const WS_EDIT_VENT: u32 = KIND_VENT;

/// Length of the hex state hash written by [`ws_world_state_hash`].
pub const WS_HASH_LEN: usize = 64;

/// Largest compressed save [`ws_world_load`] accepts (the decompressed cap is
/// `save::MAX_SAVE_BYTES`; a front-end should still expect up to about 1 GiB of peak memory).
pub const WS_MAX_SAVE_LEN: usize = 256 * 1024 * 1024;

/// Largest config object [`ws_world_create`] accepts (as `worldgen.MAX_FORM_BYTES`).
pub const WS_MAX_CONFIG_LEN: usize = 64 * 1024;

/// An opaque world handle.
pub struct WsWorld {
    world: World,
    poisoned: bool,
}

/// Read-only sizes and counters of a world.
#[repr(C)]
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct WsInfo {
    pub width: u32,
    pub height: u32,
    pub step_count: u64,
    pub population: u64,
    pub births: u64,
    pub deaths: u64,
    pub kills: u64,
    /// `World.light_factor(step_count)`: the day/season factor of the light the world holds (ADR-0016).
    pub light_factor: f64,
}

// The layout C# mirrors (`LayoutKind.Sequential`: two uint, five ulong, one double); a change bumps the ABI.
const _: () = assert!(std::mem::size_of::<WsInfo>() == 56 && std::mem::align_of::<WsInfo>() == 8);

/// One cell's inspector record (ADR-0016 Decision 2); all zero with `present` 0 on an empty tile.
#[repr(C)]
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct WsCell {
    pub id: u64,
    pub lineage: u64,
    pub age: u64,
    pub energy: f64,
    /// The fixed genome, `GENE_NAMES` order.
    pub genes: [f64; crate::N_GENES],
    /// Feeding shares: photo, sapro, pred, chemo.
    pub shares: [f64; 4],
    /// `TRAITS` order: sex_p, plast_p, hgt_p, armor_p, sense_r.
    pub traits: [f64; N_TRAITS],
    pub present: u32,
    pub bonds: u32,
    /// Cells in its bonded component, itself included (1 when unbonded).
    pub colony: u32,
    /// Number of F4 rule genes.
    pub rules: u32,
}

// The layout C# mirrors: three ulong, 1 + 16 + 4 + 5 doubles, four uint; a change bumps the ABI.
const _: () = assert!(std::mem::size_of::<WsCell>() == 248 && std::mem::align_of::<WsCell>() == 8);

thread_local! {
    static LAST_ERROR: RefCell<String> = const { RefCell::new(String::new()) };
}

fn set_error(message: impl fmt::Display) {
    // `try_with`: never panic, even during thread teardown.
    let _ = LAST_ERROR.try_with(|e| *e.borrow_mut() = crate::bounded(message));
}

fn panic_message(payload: &(dyn std::any::Any + Send)) -> String {
    let text = payload
        .downcast_ref::<&str>()
        .copied()
        .or_else(|| payload.downcast_ref::<String>().map(String::as_str))
        .unwrap_or("unknown");
    format!("internal error (panic caught): {text}")
}

fn fail(code: i32, message: impl fmt::Display) -> i32 {
    set_error(message);
    code
}

/// Run `f` on a live, unpoisoned handle with exclusive access; a panic poisons the handle.
///
/// # Safety
/// `handle` is null or a live handle (see the module contract), not used by another call meanwhile.
unsafe fn with_world_mut(handle: *mut WsWorld, f: impl FnOnce(&mut World) -> i32) -> i32 {
    // SAFETY: the caller guarantees a null or live, unaliased handle.
    let Some(h) = (unsafe { handle.as_mut() }) else {
        return fail(WS_ERR_ARGUMENT, "null world handle");
    };
    if h.poisoned {
        return fail(WS_ERR_POISONED, "world handle poisoned by an earlier panic");
    }
    match catch_unwind(AssertUnwindSafe(|| f(&mut h.world))) {
        Ok(code) => code,
        Err(payload) => {
            h.poisoned = true; // the world may be half-updated
            fail(WS_ERR_PANIC, panic_message(&*payload))
        }
    }
}

/// Run `f` on a live, unpoisoned handle with shared access (read-only views).
///
/// # Safety
/// `handle` is null or a live handle (see the module contract), not being stepped meanwhile.
unsafe fn with_world(handle: *const WsWorld, f: impl FnOnce(&World) -> i32) -> i32 {
    // SAFETY: the caller guarantees a null or live handle with no concurrent writer.
    let Some(h) = (unsafe { handle.as_ref() }) else {
        return fail(WS_ERR_ARGUMENT, "null world handle");
    };
    if h.poisoned {
        return fail(WS_ERR_POISONED, "world handle poisoned by an earlier panic");
    }
    match catch_unwind(AssertUnwindSafe(|| f(&h.world))) {
        Ok(code) => code,
        Err(payload) => fail(WS_ERR_PANIC, panic_message(&*payload)),
    }
}

/// The ABI version this library implements ([`WS_ABI_VERSION`]).
#[no_mangle]
pub extern "C" fn ws_abi_version() -> u32 {
    WS_ABI_VERSION
}

/// Load a gzip save from `len` bytes at `data`. Returns a handle, or null on failure.
///
/// # Safety
/// `data` is null or points to `len` readable bytes.
#[no_mangle]
pub unsafe extern "C" fn ws_world_load(data: *const u8, len: usize) -> *mut WsWorld {
    if data.is_null() || len == 0 {
        set_error("empty save data");
        return std::ptr::null_mut();
    }
    if len > WS_MAX_SAVE_LEN {
        set_error(format_args!(
            "save data larger than {WS_MAX_SAVE_LEN} bytes"
        ));
        return std::ptr::null_mut();
    }
    // SAFETY: checked non-null; the caller guarantees `len` readable bytes.
    let bytes = unsafe { std::slice::from_raw_parts(data, len) };
    match catch_unwind(|| world_from_gzip(bytes, MAX_SAVE_BYTES)) {
        Ok(Ok(world)) => Box::into_raw(Box::new(WsWorld {
            world,
            poisoned: false,
        })),
        Ok(Err(e)) => {
            set_error(e.message());
            std::ptr::null_mut()
        }
        Err(payload) => {
            set_error(panic_message(&*payload));
            std::ptr::null_mut()
        }
    }
}

/// Create a world from a config object (UTF-8 JSON, `Config.to_dict()` as a save stores it, exported
/// by `scripts/unity_sync.py`) and a seed, as Python's `World(cfg, seed)`: procedural terrain, then
/// `initial_cells` founders. Returns a handle, or null with the reason in [`ws_last_error`]. The
/// config is checked like a save's (every key, no unknown or duplicate key, `Config.validate()`
/// bounds); creation work is bounded by them (at most 10^6 tiles and 100 vents: under 0.3 s in release;
/// 10^6 founders take about 0.4 GB). It blocks the calling thread.
///
/// # Safety
/// `config_json` is null or points to `len` readable bytes.
#[no_mangle]
pub unsafe extern "C" fn ws_world_create(
    config_json: *const u8,
    len: usize,
    seed: u64,
) -> *mut WsWorld {
    if config_json.is_null() || len == 0 {
        set_error("empty config");
        return std::ptr::null_mut();
    }
    if len > WS_MAX_CONFIG_LEN {
        set_error(format_args!("config larger than {WS_MAX_CONFIG_LEN} bytes"));
        return std::ptr::null_mut();
    }
    // SAFETY: checked non-null; the caller guarantees `len` readable bytes.
    let bytes = unsafe { std::slice::from_raw_parts(config_json, len) };
    match catch_unwind(|| config_from_json(bytes).map(|cfg| World::new(cfg, seed))) {
        Ok(Ok(world)) => Box::into_raw(Box::new(WsWorld {
            world,
            poisoned: false,
        })),
        Ok(Err(e)) => {
            set_error(e.message());
            std::ptr::null_mut()
        }
        Err(payload) => {
            set_error(panic_message(&*payload));
            std::ptr::null_mut()
        }
    }
}

/// Release a handle. Null is ignored.
///
/// # Safety
/// `handle` is null or a live handle (see the module contract), not used afterwards.
#[no_mangle]
pub unsafe extern "C" fn ws_world_free(handle: *mut WsWorld) {
    if !handle.is_null() {
        // SAFETY: the caller hands back ownership of a pointer made by `Box::into_raw`.
        let _ = catch_unwind(AssertUnwindSafe(|| drop(unsafe { Box::from_raw(handle) })));
    }
}

/// Advance the world by `steps` steps. The call blocks until done and cannot be cancelled:
/// a front-end steps in small per-frame chunks.
///
/// # Safety
/// `handle` is null or a live handle (see the module contract).
#[no_mangle]
pub unsafe extern "C" fn ws_world_step(handle: *mut WsWorld, steps: u32) -> i32 {
    // SAFETY: forwarded caller guarantee.
    unsafe {
        with_world_mut(handle, |w| {
            for _ in 0..steps {
                w.step();
            }
            WS_OK
        })
    }
}

/// Apply one G1 edit between steps (`worldsim/play.py`, bit-exact; ADR-0013) and write its value into
/// `*out_changed`: tiles changed for nutrients, raise rock and dig, cells killed for a meteorite, 1 or 0
/// (on rock) for a vent. `kind` is a `WS_EDIT_*` code; `radius` is unused (must be 0) for a vent and
/// `amount` (organic per tile for nutrients, `max_chem` for a vent) must be 0 for the other kinds.
/// Refused with [`WS_ERR_INVALID`], the reason in [`ws_last_error`], `*out_changed` untouched and the
/// world unchanged: an unknown kind, a tile outside the world, a used unused argument, an amount that
/// is NaN, infinite or negative (`-0.0` included), or nutrients that would leave more than
/// `world::MAX_EDIT_ORGANIC` (1e12) on a tile, so later steps stay finite. Work is O(width * height) per call (at most 10^6 tiles); it blocks the calling thread.
///
/// # Safety
/// `handle` as for [`ws_world_step`]; `out_changed` is null or writable.
#[no_mangle]
pub unsafe extern "C" fn ws_world_intervene(
    handle: *mut WsWorld,
    kind: u32,
    x: u32,
    y: u32,
    radius: u32,
    amount: f64,
    out_changed: *mut u64,
) -> i32 {
    if out_changed.is_null() {
        return fail(WS_ERR_ARGUMENT, "null out_changed pointer");
    }
    // SAFETY: forwarded caller guarantee; `out_changed` checked non-null.
    unsafe {
        with_world_mut(handle, |w| {
            match Intervention::from_raw(kind, x, y, radius, amount).and_then(|iv| w.intervene(iv))
            {
                Ok(changed) => {
                    *out_changed = changed;
                    WS_OK
                }
                Err(e) => fail(WS_ERR_INVALID, e.message()),
            }
        })
    }
}

/// Copy sizes and counters into `*out`.
///
/// # Safety
/// `handle` as for [`ws_world_step`]; `out` is null or writable.
#[no_mangle]
pub unsafe extern "C" fn ws_world_info(handle: *const WsWorld, out: *mut WsInfo) -> i32 {
    if out.is_null() {
        return fail(WS_ERR_ARGUMENT, "null info pointer");
    }
    // SAFETY: forwarded caller guarantee; `out` checked non-null.
    unsafe {
        with_world(handle, |w| {
            *out = WsInfo {
                width: w.width as u32,
                height: w.height as u32,
                step_count: w.step_count,
                population: w.population() as u64,
                births: w.counters.births,
                deaths: w.counters.deaths,
                kills: w.counters.kills,
                light_factor: w.light_factor(w.step_count),
            };
            WS_OK
        })
    }
}

/// Write the 64-character hex state hash (no terminator) into `out`, which must hold
/// exactly [`WS_HASH_LEN`] bytes.
///
/// # Safety
/// `handle` as for [`ws_world_step`]; `out` is null or points to `len` writable bytes.
#[no_mangle]
pub unsafe extern "C" fn ws_world_state_hash(
    handle: *const WsWorld,
    out: *mut u8,
    len: usize,
) -> i32 {
    if out.is_null() || len != WS_HASH_LEN {
        return fail(
            WS_ERR_ARGUMENT,
            format!("hash buffer must be {WS_HASH_LEN} bytes"),
        );
    }
    // SAFETY: forwarded caller guarantee; `out` checked non-null with `len` bytes.
    unsafe {
        with_world(handle, |w| {
            let hash = state_hash(w);
            std::slice::from_raw_parts_mut(out, len).copy_from_slice(hash.as_bytes());
            WS_OK
        })
    }
}

/// Render the world as RGB (row 0 = the lit surface) into `out`, which must hold exactly
/// `width * height * 3` bytes.
///
/// # Safety
/// `handle` as for [`ws_world_step`]; `out` is null or points to `len` writable bytes.
#[no_mangle]
pub unsafe extern "C" fn ws_world_render_rgb(
    handle: *const WsWorld,
    out: *mut u8,
    len: usize,
) -> i32 {
    if out.is_null() {
        return fail(WS_ERR_ARGUMENT, "null render buffer");
    }
    // SAFETY: forwarded caller guarantee; `out` checked non-null, its size checked below.
    unsafe {
        with_world(handle, |w| {
            let need = rgb_len(w);
            if len != need {
                return fail(
                    WS_ERR_ARGUMENT,
                    format!("render buffer must be {need} bytes, got {len}"),
                );
            }
            render_rgb(w, std::slice::from_raw_parts_mut(out, len));
            WS_OK
        })
    }
}

/// Write the tile snapshot (ADR-0016 Decision 1) into `out`, which must hold exactly
/// `width * height * 4` bytes: one little-endian 32-bit word per tile, row 0 = the lit surface, so the
/// buffer is an RGBA32 image. Read-only (the state hash is unchanged); O(width * height).
///
/// # Safety
/// `handle` as for [`ws_world_step`]; `out` is null or points to `len` writable bytes.
#[no_mangle]
pub unsafe extern "C" fn ws_world_tiles(handle: *const WsWorld, out: *mut u8, len: usize) -> i32 {
    if out.is_null() {
        return fail(WS_ERR_ARGUMENT, "null tile buffer");
    }
    // SAFETY: forwarded caller guarantee; `out` checked non-null, its size checked below.
    unsafe {
        with_world(handle, |w| {
            let need = tiles_len(w);
            if len != need {
                return fail(
                    WS_ERR_ARGUMENT,
                    format!("tile buffer must be {need} bytes, got {len}"),
                );
            }
            tile_words(w, std::slice::from_raw_parts_mut(out, len));
            WS_OK
        })
    }
}

/// Write the record of the cell on tile (`x`, `y`) into `*out` (ADR-0016 Decision 2): `present` 1, or 0
/// with every field 0 on an empty tile (not an error). A tile outside the world is refused with
/// [`WS_ERR_INVALID`], `*out` untouched; the handle stays usable. Read-only; the colony walk is
/// O(colony size) plus one mark per cell slot.
///
/// # Safety
/// `handle` as for [`ws_world_step`]; `out` is null or points to a writable, 8-byte-aligned [`WsCell`].
#[no_mangle]
pub unsafe extern "C" fn ws_world_cell(
    handle: *const WsWorld,
    x: u32,
    y: u32,
    out: *mut WsCell,
) -> i32 {
    if out.is_null() {
        return fail(WS_ERR_ARGUMENT, "null cell pointer");
    }
    // SAFETY: forwarded caller guarantee; `out` checked non-null.
    unsafe {
        with_world(handle, |w| {
            let (x, y) = (x as usize, y as usize);
            if x >= w.width || y >= w.height {
                return fail(
                    WS_ERR_INVALID,
                    format!("tile ({x}, {y}) outside the {}x{} world", w.width, w.height),
                );
            }
            *out = match cell_record(w, x, y) {
                None => WsCell::default(),
                Some(r) => WsCell {
                    id: r.id,
                    lineage: r.lineage,
                    age: r.age,
                    energy: r.energy,
                    genes: r.genes,
                    shares: r.shares,
                    traits: r.traits,
                    present: 1,
                    bonds: r.bonds,
                    colony: r.colony,
                    rules: r.rules,
                },
            };
            WS_OK
        })
    }
}

/// Copy the last error message of this thread (UTF-8, no terminator, at most
/// `MAX_MESSAGE` + 3 bytes) into `out`, truncated to `len` bytes (a cut may split a UTF-8
/// sequence). Returns the full message length, so a caller can retry with a larger buffer;
/// `out` may be null to query the length. The message is not cleared on success.
///
/// # Safety
/// `out` is null or points to `len` writable bytes.
#[no_mangle]
pub unsafe extern "C" fn ws_last_error(out: *mut u8, len: usize) -> usize {
    LAST_ERROR
        .try_with(|e| {
            let e = e.borrow();
            if !out.is_null() {
                let n = e.len().min(len);
                // SAFETY: checked non-null; the caller guarantees `len` writable bytes.
                unsafe { std::slice::from_raw_parts_mut(out, n) }
                    .copy_from_slice(&e.as_bytes()[..n]);
            }
            e.len()
        })
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_panic_in_a_step_poisons_the_handle() {
        let world = crate::save::load_world(
            std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("tests/golden/default/start.json.gz"),
        )
        .expect("golden save");
        let h = Box::into_raw(Box::new(WsWorld {
            world,
            poisoned: false,
        }));
        unsafe {
            let code = with_world_mut(h, |_| panic!("boom"));
            assert_eq!(code, WS_ERR_PANIC);
            assert_eq!(ws_world_step(h, 1), WS_ERR_POISONED);
            let mut info = WsInfo::default();
            assert_eq!(ws_world_info(h, &mut info), WS_ERR_POISONED);
            let mut hash = [0u8; WS_HASH_LEN];
            assert_eq!(
                ws_world_state_hash(h, hash.as_mut_ptr(), WS_HASH_LEN),
                WS_ERR_POISONED
            );
            let mut rgb = vec![0u8; 3];
            assert_eq!(ws_world_render_rgb(h, rgb.as_mut_ptr(), 3), WS_ERR_POISONED);
            let mut tiles = vec![0u8; 4];
            assert_eq!(ws_world_tiles(h, tiles.as_mut_ptr(), 4), WS_ERR_POISONED);
            let mut cell = WsCell::default();
            assert_eq!(ws_world_cell(h, 0, 0, &mut cell), WS_ERR_POISONED);
            let mut changed = 7u64;
            assert_eq!(
                ws_world_intervene(h, WS_EDIT_NUTRIENTS, 1, 1, 2, 15.0, &mut changed),
                WS_ERR_POISONED
            );
            assert_eq!(changed, 7);
            ws_world_free(h);
        }
    }
}
