//! CPython 3.12 `random.Random`, reproduced draw for draw (G2 milestone M1b).
//!
//! The engine draws every random number from one `random.Random(seed)`; the kernel restores
//! that generator from a save (`getstate()`: 624 MT19937 words, the position index and the
//! cached `gauss_next`) and must then produce the identical stream. Only the methods the engine
//! calls are ported: `random`, `getrandbits`, `_randbelow`, `randrange(n)`, `choice`, `shuffle`
//! and `gauss`. Each mirrors CPython's `Modules/_randommodule.c` or `Lib/random.py`, including
//! the order in which it consumes words, which is what makes the stream match.
//!
//! Seeding (ADR-0012): `random.Random(n)` for a `u64` and `random.Random(s)` for a `str`, as
//! CPython's `random_seed` and `init_by_array` do it; `None`, negative and bytes seeds are not
//! ported (the kernel takes `u64` seeds only).

use std::fmt;

/// The 32-bit words of the non-negative integer whose big-endian bytes are `bytes`, least
/// significant first, without high zero words and at least one (CPython's `random_seed` key).
fn words_of_big_endian(bytes: &[u8]) -> Vec<u32> {
    let mut words: Vec<u32> = bytes
        .rchunks(4)
        .map(|c| c.iter().fold(0u32, |w, &b| (w << 8) | u32::from(b)))
        .collect();
    while words.len() > 1 && words.last() == Some(&0) {
        words.pop();
    }
    if words.is_empty() {
        words.push(0);
    }
    words
}

/// MT19937 state size in 32-bit words.
pub const MT_N: usize = 624;
const MT_M: usize = 397;
const MATRIX_A: u32 = 0x9908_b0df;
const UPPER_MASK: u32 = 0x8000_0000;
const LOWER_MASK: u32 = 0x7fff_ffff;

/// `random.TWOPI` (`2.0 * math.pi`).
const TWOPI: f64 = 2.0 * std::f64::consts::PI;

/// A state that CPython's `Random.setstate` would refuse (saves are untrusted input).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RngStateError {
    /// The internal state must be 624 words plus the position index.
    WrongLength(usize),
    /// The position index must lie in `0..=624`.
    BadIndex(u32),
}

impl fmt::Display for RngStateError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::WrongLength(n) => write!(
                f,
                "RNG state has {n} words, expected {} (624 MT words + index)",
                MT_N + 1
            ),
            Self::BadIndex(i) => write!(f, "RNG state index {i} is outside 0..={MT_N}"),
        }
    }
}

impl std::error::Error for RngStateError {}

/// CPython-compatible Mersenne Twister generator (`random.Random`).
#[derive(Debug, Clone, PartialEq)]
pub struct PyRandom {
    mt: [u32; MT_N],
    index: usize,
    gauss_next: Option<f64>,
}

impl PyRandom {
    /// Restore from `Random.getstate()`: `internal` is element 1 of that tuple (624 words then
    /// the position index), `gauss_next` element 2.
    pub fn from_state(internal: &[u32], gauss_next: Option<f64>) -> Result<Self, RngStateError> {
        if internal.len() != MT_N + 1 {
            return Err(RngStateError::WrongLength(internal.len()));
        }
        let index = internal[MT_N];
        if index as usize > MT_N {
            return Err(RngStateError::BadIndex(index));
        }
        let mut mt = [0u32; MT_N];
        mt.copy_from_slice(&internal[..MT_N]);
        Ok(Self {
            mt,
            index: index as usize,
            gauss_next,
        })
    }

    /// The inverse of [`PyRandom::from_state`]: 625 words and the cached gauss value.
    pub fn state(&self) -> (Vec<u32>, Option<f64>) {
        let mut words = self.mt.to_vec();
        words.push(self.index as u32);
        (words, self.gauss_next)
    }

    /// `random.Random(seed)` for a non-negative integer seed (ADR-0012): the seed's 32-bit words,
    /// least significant first and at least one (`0` gives `[0]`), through `init_by_array`.
    pub fn from_seed_u64(seed: u64) -> Self {
        let (low, high) = (seed as u32, (seed >> 32) as u32);
        if high == 0 {
            Self::from_key(&[low])
        } else {
            Self::from_key(&[low, high])
        }
    }

    /// `random.Random(s)` for a `str` seed (version 2): `int.from_bytes(b + sha512(b), "big")`
    /// with `b = s.encode()`, then the integer path on that (large, positive) number.
    pub fn from_seed_str(s: &str) -> Self {
        use sha2::{Digest, Sha512};
        let mut bytes = s.as_bytes().to_vec();
        bytes.extend_from_slice(&Sha512::digest(s.as_bytes()));
        Self::from_key(&words_of_big_endian(&bytes))
    }

    /// `init_by_array` (which starts with `init_genrand(19650218)`); index 624, no cached gauss.
    fn from_key(key: &[u32]) -> Self {
        let mut mt = [0u32; MT_N];
        mt[0] = 19_650_218;
        for i in 1..MT_N {
            mt[i] = 1_812_433_253u32
                .wrapping_mul(mt[i - 1] ^ (mt[i - 1] >> 30))
                .wrapping_add(i as u32);
        }
        let (mut i, mut j) = (1usize, 0usize);
        for _ in 0..MT_N.max(key.len()) {
            mt[i] = (mt[i] ^ (mt[i - 1] ^ (mt[i - 1] >> 30)).wrapping_mul(1_664_525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= MT_N {
                mt[0] = mt[MT_N - 1];
                i = 1;
            }
            if j >= key.len() {
                j = 0;
            }
        }
        for _ in 0..MT_N - 1 {
            mt[i] = (mt[i] ^ (mt[i - 1] ^ (mt[i - 1] >> 30)).wrapping_mul(1_566_083_941))
                .wrapping_sub(i as u32);
            i += 1;
            if i >= MT_N {
                mt[0] = mt[MT_N - 1];
                i = 1;
            }
        }
        mt[0] = 0x8000_0000;
        Self {
            mt,
            index: MT_N,
            gauss_next: None,
        }
    }

    /// `genrand_uint32` from `_randommodule.c`.
    fn next_u32(&mut self) -> u32 {
        if self.index >= MT_N {
            self.regenerate();
        }
        let mut y = self.mt[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c_5680;
        y ^= (y << 15) & 0xefc6_0000;
        y ^ (y >> 18)
    }

    fn regenerate(&mut self) {
        let mag01 = |y: u32| if y & 1 == 0 { 0 } else { MATRIX_A };
        for kk in 0..MT_N - MT_M {
            let y = (self.mt[kk] & UPPER_MASK) | (self.mt[kk + 1] & LOWER_MASK);
            self.mt[kk] = self.mt[kk + MT_M] ^ (y >> 1) ^ mag01(y);
        }
        for kk in MT_N - MT_M..MT_N - 1 {
            let y = (self.mt[kk] & UPPER_MASK) | (self.mt[kk + 1] & LOWER_MASK);
            self.mt[kk] = self.mt[kk + MT_M - MT_N] ^ (y >> 1) ^ mag01(y);
        }
        let y = (self.mt[MT_N - 1] & UPPER_MASK) | (self.mt[0] & LOWER_MASK);
        self.mt[MT_N - 1] = self.mt[MT_M - 1] ^ (y >> 1) ^ mag01(y);
        self.index = 0;
    }

    /// `random()`: a float in [0, 1) with 53 random bits (`a >> 5`, `b >> 6`).
    pub fn random(&mut self) -> f64 {
        let a = self.next_u32() >> 5;
        let b = self.next_u32() >> 6;
        (a as f64 * 67_108_864.0 + b as f64) * (1.0 / 9_007_199_254_740_992.0)
    }

    /// `getrandbits(k)` for `k <= 64`. Words are drawn least significant first; the last word
    /// keeps its top `k mod 32` bits, as CPython does.
    pub fn getrandbits(&mut self, k: u32) -> u64 {
        assert!(k <= 64, "getrandbits supports k <= 64, got {k}");
        if k <= 32 {
            return if k == 0 {
                0
            } else {
                u64::from(self.next_u32() >> (32 - k))
            };
        }
        let mut result = 0u64;
        let mut remaining = k;
        let mut shift = 0;
        while remaining > 0 {
            let mut word = self.next_u32();
            if remaining < 32 {
                word >>= 32 - remaining;
            }
            result |= u64::from(word) << shift;
            shift += 32;
            remaining = remaining.saturating_sub(32);
        }
        result
    }

    /// `_randbelow_with_getrandbits(n)`: rejection sampling on `n.bit_length()` bits.
    pub fn randbelow(&mut self, n: u64) -> u64 {
        assert!(n > 0, "randbelow needs n > 0");
        let k = u64::BITS - n.leading_zeros();
        loop {
            let r = self.getrandbits(k);
            if r < n {
                return r;
            }
        }
    }

    /// `randrange(n)` with a single argument.
    pub fn randrange(&mut self, n: u64) -> u64 {
        assert!(n > 0, "empty range for randrange()");
        self.randbelow(n)
    }

    /// `choice(seq)`: `seq[_randbelow(len(seq))]`.
    pub fn choice<'a, T>(&mut self, seq: &'a [T]) -> &'a T {
        assert!(!seq.is_empty(), "cannot choose from an empty sequence");
        &seq[self.randbelow(seq.len() as u64) as usize]
    }

    /// `shuffle(x)`: Fisher–Yates from the last element down, `j = _randbelow(i + 1)`.
    pub fn shuffle<T>(&mut self, x: &mut [T]) {
        for i in (1..x.len()).rev() {
            let j = self.randbelow(i as u64 + 1) as usize;
            x.swap(i, j);
        }
    }

    /// `gauss(mu, sigma)`: Box–Muller producing a pair; the second value is cached in
    /// `gauss_next` and survives intervening `random()` calls, as in CPython.
    pub fn gauss(&mut self, mu: f64, sigma: f64) -> f64 {
        let z = match self.gauss_next.take() {
            Some(z) => z,
            None => {
                let x2pi = self.random() * TWOPI;
                let g2rad = (-2.0 * (1.0 - self.random()).ln()).sqrt();
                self.gauss_next = Some(x2pi.sin() * g2rad);
                x2pi.cos() * g2rad
            }
        };
        mu + z * sigma
    }
}
