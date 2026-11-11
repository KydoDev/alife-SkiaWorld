//! M4: the kernel's render equals Python's `render_rgb` byte for byte, on the loaded start save
//! (which also checks the light computed at load) and after the golden steps.

mod common;

use common::{golden_dir, hashes, GOLDEN_SETS};
use flate2::read::GzDecoder;
use std::io::Read;
use worldsim_core::render::{render_rgb, rgb_len};
use worldsim_core::save::load_world;
use worldsim_core::world::World;

fn golden_render(set: &str, name: &str) -> Vec<u8> {
    let path = golden_dir(set).join(name);
    let file = std::fs::File::open(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    let mut out = Vec::new();
    GzDecoder::new(file).read_to_end(&mut out).expect("gzip");
    out
}

fn assert_render(set: &str, name: &str, world: &World) {
    let want = golden_render(set, name);
    let mut got = vec![0u8; rgb_len(world)];
    render_rgb(world, &mut got);
    assert_eq!(got.len(), want.len(), "{set}/{name}: size");
    if let Some(i) = (0..got.len()).find(|&i| got[i] != want[i]) {
        let (px, w) = (i / 3, world.width);
        let differing = (0..got.len()).filter(|&j| got[j] != want[j]).count();
        panic!(
            "{set}/{name}: first difference at (x {}, y {}) channel {}: {} vs Python {} ({differing} bytes differ)",
            px % w,
            px / w,
            i % 3,
            got[i],
            want[i]
        );
    }
}

#[test]
fn render_matches_python_at_start_and_after_the_golden_steps() {
    for set in GOLDEN_SETS {
        let mut world = load_world(golden_dir(set).join("start.json.gz")).expect("start save");
        assert_render(set, "render_start.rgb.gz", &world);
        let steps = hashes(set).len() - 1;
        for _ in 0..steps {
            world.step();
        }
        assert_render(set, "render_end.rgb.gz", &world);
    }
}

#[test]
#[should_panic(expected = "render buffer size")]
fn render_refuses_a_wrong_buffer() {
    let world = load_world(golden_dir("default").join("start.json.gz")).expect("start save");
    render_rgb(&world, &mut vec![0u8; rgb_len(&world) - 1]);
}
