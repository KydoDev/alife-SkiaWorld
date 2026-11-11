//! World -> RGB image (`worldsim/render.py::render_rgb`), byte for byte.
//!
//! numpy computes the water in float64 and stores it in a float32 image; the vent and organic
//! blends mix float32 colours with float64 fields, which promotes the image to float64; cell
//! colours are float32 throughout. The final cast truncates. Every step below keeps that order
//! and those precisions, so the result equals Python's exactly (checked against golden renders).

use crate::world::{World, G_CHEMO, G_PHOTO, G_PRED, G_SAPRO};

const C_PHOTO: [f32; 3] = [60.0, 210.0, 70.0];
const C_SAPRO: [f32; 3] = [170.0, 90.0, 230.0];
const C_PRED: [f32; 3] = [235.0, 50.0, 45.0];
const C_CHEMO: [f32; 3] = [40.0, 215.0, 225.0];
const C_ROCK: [f32; 3] = [92.0, 88.0, 84.0];
const C_VENT: [f32; 3] = [255.0, 120.0, 20.0];
const C_ORGANIC: [f32; 3] = [120.0, 80.0, 35.0];

/// Bytes of an RGB image of `world`: `width * height * 3`.
pub fn rgb_len(world: &World) -> usize {
    world.width * world.height * 3
}

/// Render `world` into `out` (row-major RGB, row 0 = the lit surface), organic matter shown.
///
/// # Panics
/// If `out.len() != rgb_len(world)`.
pub fn render_rgb(world: &World, out: &mut [u8]) {
    assert_eq!(out.len(), rgb_len(world), "render buffer size");
    let light_max = world.cfg.light_max;
    let organic_f32: [f32; 3] = C_ORGANIC.map(|c| c * 0.8f32); // `C_ORGANIC * 0.8` (float32)
    for i in 0..world.width * world.height {
        let lum = clip01(world.light[i] / light_max);
        // float64 expressions stored into the float32 image
        let mut px: [f64; 3] = [
            f64::from((8.0 + 20.0 * lum) as f32),
            f64::from((14.0 + 45.0 * lum) as f32),
            f64::from((30.0 + 110.0 * lum) as f32),
        ];
        if world.has_chem {
            let v = clip01(world.terrain.chem[i]) * 0.6;
            for (p, c) in px.iter_mut().zip(C_VENT) {
                *p = *p * (1.0 - v) + f64::from(c) * v;
            }
        }
        let o = clip01(world.organic[i] / 20.0);
        for (p, c) in px.iter_mut().zip(organic_f32) {
            *p = *p * (1.0 - 0.8 * o) + f64::from(c) * o;
        }
        if world.has_rock && world.terrain.rock[i] {
            px = C_ROCK.map(f64::from);
        }
        write_px(out, i, px);
    }
    // Python colours cells by `c.photo` etc., which follow the acclimated diet when plasticity
    // is on. The loader refuses plasticity until M5; porting it must switch this to the diet.
    debug_assert!(
        !world.cfg.plasticity,
        "render of a plastic world needs the diet (M5)"
    );
    for c in world.cells() {
        let g = &c.genes;
        let mut s = g[G_PHOTO] + g[G_SAPRO] + g[G_PRED] + g[G_CHEMO];
        if s == 0.0 {
            s = 1e-9;
        }
        let tr = [G_PHOTO, G_SAPRO, G_PRED, G_CHEMO].map(|k| (g[k] / s) as f32);
        let bonded: f32 = if c.bonds.is_empty() { 0.0 } else { 1.0 };
        let factor = 0.85f32 + 0.15f32 * bonded;
        let mut px = [0.0f64; 3];
        for (k, p) in px.iter_mut().enumerate() {
            let col =
                tr[0] * C_PHOTO[k] + tr[1] * C_SAPRO[k] + tr[2] * C_PRED[k] + tr[3] * C_CHEMO[k];
            *p = f64::from(col * factor + 25.0f32 * bonded);
        }
        write_px(out, c.y * world.width + c.x, px);
    }
}

/// `np.clip(v, 0, 1)`.
fn clip01(v: f64) -> f64 {
    v.clamp(0.0, 1.0)
}

/// `np.clip(img, 0, 255).astype(np.uint8)`: clip, then truncate.
fn write_px(out: &mut [u8], i: usize, px: [f64; 3]) {
    for (k, p) in px.into_iter().enumerate() {
        out[3 * i + k] = p.clamp(0.0, 255.0) as u8;
    }
}
