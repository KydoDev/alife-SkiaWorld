//! numpy reductions the Python engine relies on, reproduced bit for bit (ADR-0012).
//!
//! `ndarray.mean()` of a contiguous `float64` array is `add.reduce` (numpy's pairwise summation,
//! `pairwise_sum_DOUBLE` in `loops_utils.h.src`) divided by the element count.

/// numpy's blocking for pairwise summation: below 8 elements a plain loop, up to this many eight
/// interleaved accumulators, above it a recursive split.
const PW_BLOCKSIZE: usize = 128;

/// `pairwise_sum_DOUBLE` on a contiguous slice.
fn pairwise_sum(a: &[f64]) -> f64 {
    let n = a.len();
    if n < 8 {
        let mut res = 0.0f64;
        for &v in a {
            res += v;
        }
        res
    } else if n <= PW_BLOCKSIZE {
        let mut r = [0.0f64; 8];
        r.copy_from_slice(&a[..8]);
        let mut i = 8;
        while i < n - (n % 8) {
            for (k, acc) in r.iter_mut().enumerate() {
                *acc += a[i + k];
            }
            i += 8;
        }
        let mut res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for &v in &a[i..] {
            res += v;
        }
        res
    } else {
        let mut n2 = n / 2;
        n2 -= n2 % 8;
        pairwise_sum(&a[..n2]) + pairwise_sum(&a[n2..])
    }
}

/// `np.add.reduce` of a contiguous 1-D `float64` array: numpy's identity `+0.0` seeds the
/// accumulator and the whole array is summed pairwise (the golden vectors rule out seeding with the
/// first element; numpy also returns `+0.0` for a sum of `-0.0`).
pub fn numpy_sum(a: &[f64]) -> f64 {
    0.0 + pairwise_sum(a)
}

/// `ndarray.mean()` of a non-empty contiguous 1-D `float64` array: [`numpy_sum`] / `len`.
pub fn numpy_mean(a: &[f64]) -> f64 {
    numpy_sum(a) / a.len() as f64
}

#[doc(hidden)]
/// `pairwise_sum_DOUBLE` itself, for tests that compare the candidates.
pub fn pairwise(a: &[f64]) -> f64 {
    pairwise_sum(a)
}
