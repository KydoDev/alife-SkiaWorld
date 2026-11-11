//! C ABI for front-ends (G2 M4: Unity through P/Invoke).
//!
//! Only what `docs/G2_PLAN.md` allows across the boundary: loading a save, stepping, and
//! read-only views (sizes, state hash, an RGB render). Nothing writes world fields.
//!
//! Contract for every function:
//! - A world is an opaque handle from [`ws_world_load`], released with [`ws_world_free`].
//! - Status codes: [`WS_OK`] (0) or a negative error; the message of the last failure on this
//!   thread is copied out by [`ws_last_error`].
//! - Pointers are checked for null and buffers for their exact length; no panic crosses the
//!   boundary (each entry point runs inside `catch_unwind`). A panic inside a step may leave the
//!   world half-updated, so the handle is then poisoned and every later call on it fails.
//! - A handle must not be used from two threads at once, nor after it is freed.

use crate::hash::state_hash;
use crate::render::{render_rgb, rgb_len};
use crate::save::{world_from_gzip, MAX_SAVE_BYTES};
use crate::world::World;
use std::cell::RefCell;
use std::panic::{catch_unwind, AssertUnwindSafe};

/// Bumped whenever a signature or a struct below changes; front-ends refuse a mismatch.
pub const WS_ABI_VERSION: u32 = 1;

pub const WS_OK: i32 = 0;
/// A null pointer or a buffer of the wrong size.
pub const WS_ERR_ARGUMENT: i32 = -1;
/// The save was refused (malformed, hostile, or needs a feature this kernel lacks).
pub const WS_ERR_LOAD: i32 = -2;
/// A panic was caught; the handle, if any, is now poisoned.
pub const WS_ERR_PANIC: i32 = -3;
/// The handle was poisoned by an earlier panic.
pub const WS_ERR_POISONED: i32 = -4;

/// Length of the hex state hash written by [`ws_world_state_hash`].
pub const WS_HASH_LEN: usize = 64;

/// An opaque world handle.
pub struct WsWorld {
    world: World,
    poisoned: bool,
}

/// Read-only sizes and counters of a world.
#[repr(C)]
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct WsInfo {
    pub width: u32,
    pub height: u32,
    pub step_count: u64,
    pub population: u64,
    pub births: u64,
    pub deaths: u64,
    pub kills: u64,
}

thread_local! {
    static LAST_ERROR: RefCell<String> = const { RefCell::new(String::new()) };
}

fn set_error(message: impl Into<String>) {
    LAST_ERROR.with(|e| *e.borrow_mut() = message.into());
}

fn fail(code: i32, message: impl Into<String>) -> i32 {
    set_error(message);
    code
}

/// Run `f` on a live, unpoisoned handle; a panic poisons it when `poison_on_panic`.
///
/// # Safety
/// `handle` is null or a live pointer from [`ws_world_load`].
unsafe fn with_world(
    handle: *mut WsWorld,
    poison_on_panic: bool,
    f: impl FnOnce(&mut World) -> i32,
) -> i32 {
    // SAFETY: the caller guarantees a null or live, unaliased handle.
    let Some(h) = (unsafe { handle.as_mut() }) else {
        return fail(WS_ERR_ARGUMENT, "null world handle");
    };
    if h.poisoned {
        return fail(WS_ERR_POISONED, "world handle poisoned by an earlier panic");
    }
    match catch_unwind(AssertUnwindSafe(|| f(&mut h.world))) {
        Ok(code) => code,
        Err(_) => {
            if poison_on_panic {
                h.poisoned = true;
            }
            fail(WS_ERR_PANIC, "internal error (panic caught)")
        }
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
        Err(_) => {
            set_error("internal error while loading (panic caught)");
            std::ptr::null_mut()
        }
    }
}

/// Release a handle. Null is ignored.
///
/// # Safety
/// `handle` is null or a live pointer from [`ws_world_load`], not used afterwards.
#[no_mangle]
pub unsafe extern "C" fn ws_world_free(handle: *mut WsWorld) {
    if !handle.is_null() {
        // SAFETY: the caller hands back ownership of a pointer made by `Box::into_raw`.
        let _ = catch_unwind(AssertUnwindSafe(|| drop(unsafe { Box::from_raw(handle) })));
    }
}

/// Advance the world by `steps` steps.
///
/// # Safety
/// `handle` is null or a live pointer from [`ws_world_load`].
#[no_mangle]
pub unsafe extern "C" fn ws_world_step(handle: *mut WsWorld, steps: u32) -> i32 {
    // SAFETY: forwarded caller guarantee.
    unsafe {
        with_world(handle, true, |w| {
            for _ in 0..steps {
                w.step();
            }
            WS_OK
        })
    }
}

/// Copy sizes and counters into `*out`.
///
/// # Safety
/// `handle` as for [`ws_world_step`]; `out` is null or writable.
#[no_mangle]
pub unsafe extern "C" fn ws_world_info(handle: *mut WsWorld, out: *mut WsInfo) -> i32 {
    if out.is_null() {
        return fail(WS_ERR_ARGUMENT, "null info pointer");
    }
    // SAFETY: forwarded caller guarantee; `out` checked non-null.
    unsafe {
        with_world(handle, false, |w| {
            *out = WsInfo {
                width: w.width as u32,
                height: w.height as u32,
                step_count: w.step_count,
                population: w.population() as u64,
                births: w.counters.births,
                deaths: w.counters.deaths,
                kills: w.counters.kills,
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
    handle: *mut WsWorld,
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
        with_world(handle, false, |w| {
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
    handle: *mut WsWorld,
    out: *mut u8,
    len: usize,
) -> i32 {
    if out.is_null() {
        return fail(WS_ERR_ARGUMENT, "null render buffer");
    }
    // SAFETY: forwarded caller guarantee; `out` checked non-null, its size checked below.
    unsafe {
        with_world(handle, false, |w| {
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

/// Copy the last error message of this thread (UTF-8, no terminator) into `out`, truncated
/// to `len` bytes. Returns the full message length, so a caller can retry with a larger
/// buffer; `out` may be null to query the length.
///
/// # Safety
/// `out` is null or points to `len` writable bytes.
#[no_mangle]
pub unsafe extern "C" fn ws_last_error(out: *mut u8, len: usize) -> usize {
    LAST_ERROR.with(|e| {
        let e = e.borrow();
        if !out.is_null() {
            let n = e.len().min(len);
            // SAFETY: checked non-null; the caller guarantees `len` writable bytes.
            unsafe { std::slice::from_raw_parts_mut(out, n) }.copy_from_slice(&e.as_bytes()[..n]);
        }
        e.len()
    })
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
            let code = with_world(h, true, |_| panic!("boom"));
            assert_eq!(code, WS_ERR_PANIC);
            assert_eq!(ws_world_step(h, 1), WS_ERR_POISONED);
            let mut info = WsInfo::default();
            assert_eq!(ws_world_info(h, &mut info), WS_ERR_POISONED);
            ws_world_free(h);
        }
    }
}
