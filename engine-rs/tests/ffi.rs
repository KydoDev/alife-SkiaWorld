//! M4: the C ABI reproduces the golden hashes and refuses bad input without crashing.

mod common;

use common::{golden_dir, hashes, GOLDEN_SETS};
use worldsim_core::ffi::*;

fn last_error() -> String {
    unsafe {
        let n = ws_last_error(std::ptr::null_mut(), 0);
        let mut buf = vec![0u8; n];
        assert_eq!(ws_last_error(buf.as_mut_ptr(), n), n);
        String::from_utf8(buf).expect("utf-8 error")
    }
}

fn load_bytes(bytes: &[u8]) -> *mut WsWorld {
    unsafe { ws_world_load(bytes.as_ptr(), bytes.len()) }
}

fn hash_of(h: *mut WsWorld) -> String {
    let mut buf = [0u8; WS_HASH_LEN];
    assert_eq!(
        unsafe { ws_world_state_hash(h, buf.as_mut_ptr(), buf.len()) },
        WS_OK
    );
    String::from_utf8(buf.to_vec()).expect("hex")
}

fn golden_bytes(set: &str) -> Vec<u8> {
    std::fs::read(golden_dir(set).join("start.json.gz")).expect("golden save")
}

#[test]
fn golden_hashes_through_the_abi() {
    assert_eq!(ws_abi_version(), WS_ABI_VERSION);
    for set in GOLDEN_SETS {
        let rows = hashes(set);
        let h = load_bytes(&golden_bytes(set));
        assert!(!h.is_null(), "{set}: {}", last_error());
        assert_eq!(hash_of(h), rows[0].2, "{set}: start");
        // in uneven chunks, as a front-end at a variable speed would call it
        let (mut done, mut chunk) = (0usize, 1u32);
        while done + 1 < rows.len() {
            let n = chunk.min((rows.len() - 1 - done) as u32);
            assert_eq!(unsafe { ws_world_step(h, n) }, WS_OK);
            done += n as usize;
            assert_eq!(hash_of(h), rows[done].2, "{set}: step {}", rows[done].0);
            chunk = chunk % 37 + 7;
        }
        let mut info = WsInfo::default();
        assert_eq!(unsafe { ws_world_info(h, &mut info) }, WS_OK);
        let last = rows.last().unwrap();
        assert_eq!(
            (info.step_count, info.population),
            (last.0, last.1),
            "{set}: info"
        );
        let mut rgb = vec![0u8; info.width as usize * info.height as usize * 3];
        assert_eq!(
            unsafe { ws_world_render_rgb(h, rgb.as_mut_ptr(), rgb.len()) },
            WS_OK
        );
        assert!(rgb.iter().any(|&b| b != 0));
        unsafe { ws_world_free(h) };
    }
}

#[test]
fn bad_saves_return_null_with_a_message() {
    assert!(unsafe { ws_world_load(std::ptr::null(), 10) }.is_null());
    assert!(last_error().contains("empty"));
    assert!(load_bytes(b"not a gzip file").is_null());
    assert!(
        last_error().contains("not a valid save"),
        "{}",
        last_error()
    );
    let plain = br#"{"format": "worldsim-save", "version": 1}"#;
    let mut gz = Vec::new();
    {
        use std::io::Write;
        let mut e = flate2::write::GzEncoder::new(&mut gz, flate2::Compression::fast());
        e.write_all(plain).unwrap();
        e.finish().unwrap();
    }
    assert!(load_bytes(&gz).is_null());
    assert!(!last_error().is_empty());
}

#[test]
fn null_handles_and_wrong_buffers_are_refused() {
    let mut info = WsInfo::default();
    let mut hash = [0u8; WS_HASH_LEN];
    unsafe {
        assert_eq!(ws_world_step(std::ptr::null_mut(), 1), WS_ERR_ARGUMENT);
        assert_eq!(
            ws_world_info(std::ptr::null_mut(), &mut info),
            WS_ERR_ARGUMENT
        );
        assert_eq!(
            ws_world_state_hash(std::ptr::null_mut(), hash.as_mut_ptr(), WS_HASH_LEN),
            WS_ERR_ARGUMENT
        );
        ws_world_free(std::ptr::null_mut()); // ignored
    }
    let h = load_bytes(&golden_bytes("default"));
    assert!(!h.is_null());
    unsafe {
        assert_eq!(ws_world_info(h, std::ptr::null_mut()), WS_ERR_ARGUMENT);
        assert_eq!(
            ws_world_state_hash(h, hash.as_mut_ptr(), WS_HASH_LEN - 1),
            WS_ERR_ARGUMENT
        );
        assert_eq!(ws_world_info(h, &mut info), WS_OK);
        let mut short = vec![0u8; info.width as usize * info.height as usize * 3 - 1];
        assert_eq!(
            ws_world_render_rgb(h, short.as_mut_ptr(), short.len()),
            WS_ERR_ARGUMENT
        );
        assert!(last_error().contains("render buffer"));
        assert_eq!(
            ws_world_render_rgb(h, std::ptr::null_mut(), 0),
            WS_ERR_ARGUMENT
        );
        // the handle is still usable after refused calls
        assert_eq!(ws_world_step(h, 1), WS_OK);
        ws_world_free(h);
    }
}

#[test]
fn a_save_with_an_unsupported_flag_is_refused_with_its_reason() {
    use std::io::{Read, Write};
    let mut json = String::new();
    flate2::read::GzDecoder::new(&golden_bytes("default")[..])
        .read_to_string(&mut json)
        .unwrap();
    let json = json.replacen("\"sex\":false", "\"sex\":true", 1);
    let mut gz = Vec::new();
    let mut e = flate2::write::GzEncoder::new(&mut gz, flate2::Compression::fast());
    e.write_all(json.as_bytes()).unwrap();
    e.finish().unwrap();
    assert!(load_bytes(&gz).is_null());
    assert!(last_error().contains("sex is on"), "{}", last_error());
}

#[test]
fn a_hostile_save_cannot_make_a_huge_error_message() {
    use std::io::Write;
    let json = format!(
        r#"{{"format": "worldsim-save", "step_count": "{}"}}"#,
        "A".repeat(1_000_000)
    );
    let mut gz = Vec::new();
    let mut e = flate2::write::GzEncoder::new(&mut gz, flate2::Compression::best());
    e.write_all(json.as_bytes()).unwrap();
    e.finish().unwrap();
    assert!(load_bytes(&gz).is_null());
    let n = unsafe { ws_last_error(std::ptr::null_mut(), 0) };
    assert!(n <= worldsim_core::MAX_MESSAGE + 3, "message of {n} bytes");
    assert!(last_error().ends_with("..."));
}

#[test]
fn last_error_truncates_to_the_buffer() {
    assert!(load_bytes(b"x").is_null());
    let full = last_error();
    let mut small = [0u8; 4];
    let n = unsafe { ws_last_error(small.as_mut_ptr(), small.len()) };
    assert_eq!(n, full.len());
    assert_eq!(&small, &full.as_bytes()[..4]);
}
