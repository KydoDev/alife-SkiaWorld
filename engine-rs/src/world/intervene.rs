//! ADR-0013: the five world edits of `worldsim/play.py` (`add_nutrients`, `meteorite`, `raise_rock`, `dig`,
//! `add_vent`) plus `_finish_edit`, ported bit for bit. They run between steps, draw nothing from the RNG and
//! touch only saved state. Game rules (budget, costs, milestones) stay in Python.
//!
//! Every input is validated before the first write (Decision 3): a refused edit leaves the world bit-identical.
//! The edits index only validated tiles, and their work is O(W * H) per call, bounded by `MAX_WORLD_TILES`.

use super::{py_max, CellRef, World};
use crate::terrain::vent_plume;

/// Kind codes of `ws_world_intervene` (0 stays invalid, so zeroed memory is never an action).
pub const KIND_NUTRIENTS: u32 = 1;
pub const KIND_METEORITE: u32 = 2;
pub const KIND_RAISE_ROCK: u32 = 3;
pub const KIND_DIG: u32 = 4;
pub const KIND_VENT: u32 = 5;

/// Largest organic matter a nutrient edit may leave on a tile. Stricter than Python, which has no bound
/// (`GameRules` adds 15.0): "finite after the edit" is not enough, since the next step's diffusion sums
/// neighbours and a tile near `f64::MAX` turns the field infinite, then NaN (ADR-0013 piece 4 security
/// review). At 1e12 the diffusion sums stay far from overflow, and no game action comes near it.
pub const MAX_EDIT_ORGANIC: f64 = 1e12;

/// One edit: the record `(kind, x, y, radius, amount)` of ADR-0013 with its unused arguments dropped.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Intervention {
    /// `play.add_nutrients`: `amount` organic matter on every non-rock tile of the disc.
    Nutrients {
        x: u32,
        y: u32,
        radius: u32,
        amount: f64,
    },
    /// `play.meteorite`: every cell in the disc dies; bodies become organic matter.
    Meteorite { x: u32, y: u32, radius: u32 },
    /// `play.raise_rock`: rock rises in the disc, crushing the cells there.
    RaiseRock { x: u32, y: u32, radius: u32 },
    /// `play.dig`: rock in the disc becomes water.
    Dig { x: u32, y: u32, radius: u32 },
    /// `play.add_vent`: a vent plume at `(x, y)`, stacked tiles capped at `max_chem`.
    Vent { x: u32, y: u32, max_chem: f64 },
}

/// Why an edit was refused; the world is unchanged.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InterventionError(String);

impl InterventionError {
    fn new(msg: impl Into<String>) -> Self {
        Self(msg.into())
    }

    pub fn message(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Display for InterventionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for InterventionError {}

impl Intervention {
    /// The edit a record `(kind, x, y, radius, amount)` names. An argument the kind does not use must be exactly
    /// zero (`amount` for meteorite, rock and dig; `radius` for a vent), so that slot can never change meaning
    /// silently later. Value checks that need the world are done by [`World::intervene`].
    pub fn from_raw(
        kind: u32,
        x: u32,
        y: u32,
        radius: u32,
        amount: f64,
    ) -> Result<Self, InterventionError> {
        let no_amount = || {
            if amount.to_bits() == 0 {
                Ok(())
            } else {
                Err(InterventionError::new(format!(
                    "amount must be 0 for intervention kind {kind}, got {amount}"
                )))
            }
        };
        match kind {
            KIND_NUTRIENTS => Ok(Self::Nutrients {
                x,
                y,
                radius,
                amount,
            }),
            KIND_METEORITE => no_amount().map(|_| Self::Meteorite { x, y, radius }),
            KIND_RAISE_ROCK => no_amount().map(|_| Self::RaiseRock { x, y, radius }),
            KIND_DIG => no_amount().map(|_| Self::Dig { x, y, radius }),
            KIND_VENT if radius != 0 => Err(InterventionError::new(format!(
                "radius must be 0 for a vent, got {radius}"
            ))),
            KIND_VENT => Ok(Self::Vent {
                x,
                y,
                max_chem: amount,
            }),
            _ => Err(InterventionError::new(format!(
                "unknown intervention kind {kind}"
            ))),
        }
    }

    /// The target tile.
    pub fn tile(&self) -> (u32, u32) {
        match *self {
            Self::Nutrients { x, y, .. }
            | Self::Meteorite { x, y, .. }
            | Self::RaiseRock { x, y, .. }
            | Self::Dig { x, y, .. }
            | Self::Vent { x, y, .. } => (x, y),
        }
    }
}

/// A non-negative finite amount; `-0.0` is refused too (Python's `GameRules` never passes it, and numpy's
/// min/max ties on signed zeros are not worth matching).
fn check_amount(what: &str, v: f64) -> Result<(), InterventionError> {
    if v.is_finite() && !v.is_sign_negative() {
        Ok(())
    } else {
        Err(InterventionError::new(format!(
            "{what} must be finite and >= 0, got {v}"
        )))
    }
}

impl World {
    /// Apply one edit between steps and return Python's value: tiles changed (nutrients, rock, dig), cells
    /// killed (meteorite), or 1/0 for a vent (0 on rock). On `Err` nothing changed.
    pub fn intervene(&mut self, iv: Intervention) -> Result<u64, InterventionError> {
        self.check_intervention(&iv)?;
        Ok(match iv {
            Intervention::Nutrients {
                x,
                y,
                radius,
                amount,
            } => self.add_nutrients(x, y, radius, amount),
            Intervention::Meteorite { x, y, radius } => self.meteorite(x, y, radius),
            Intervention::RaiseRock { x, y, radius } => self.raise_rock(x, y, radius),
            Intervention::Dig { x, y, radius } => self.dig(x, y, radius),
            Intervention::Vent { x, y, max_chem } => self.add_vent(x, y, max_chem),
        })
    }

    fn check_intervention(&self, iv: &Intervention) -> Result<(), InterventionError> {
        let (x, y) = iv.tile();
        if x as usize >= self.width || y as usize >= self.height {
            return Err(InterventionError::new(format!(
                "tile ({x}, {y}) is outside the {}x{} world",
                self.width, self.height
            )));
        }
        match *iv {
            Intervention::Nutrients {
                x,
                y,
                radius,
                amount,
            } => {
                check_amount("nutrient amount", amount)?;
                // stricter than Python, which has no bound: every edited tile stays <= MAX_EDIT_ORGANIC
                let mask = self.disc(x, y, radius);
                let overflow = (0..mask.len()).any(|i| {
                    mask[i] && !self.terrain.rock[i] && {
                        let after = self.organic[i] + amount;
                        after.is_nan() || after > MAX_EDIT_ORGANIC
                    }
                });
                if overflow {
                    return Err(InterventionError::new(format!(
                        "adding {amount} would push organic matter above {MAX_EDIT_ORGANIC} on a tile"
                    )));
                }
                Ok(())
            }
            Intervention::Vent { max_chem, .. } => check_amount("max_chem", max_chem),
            _ => Ok(()),
        }
    }

    /// `play._disc`: tiles within distance `r` of `(x, y)`, toroidal in x; exact integer test (no overflow:
    /// offsets are below 10^4 and `r * r` fits in `u64` for any `u32`).
    fn disc(&self, x: u32, y: u32, r: u32) -> Vec<bool> {
        let (w, h) = (self.width, self.height);
        let (x, y) = (x as usize, y as usize);
        let r2 = u64::from(r) * u64::from(r);
        let mut mask = vec![false; w * h];
        for ys in 0..h {
            let dy = ys.abs_diff(y) as u64;
            for xs in 0..w {
                let d = xs.abs_diff(x);
                let dx = d.min(w - d) as u64;
                mask[ys * w + xs] = dx * dx + dy * dy <= r2;
            }
        }
        mask
    }

    /// Living cells on the mask, in list order (`[c for c in world.cells if c.alive and mask[c.y, c.x]]`).
    fn cells_on(&self, mask: &[bool]) -> Vec<CellRef> {
        self.order
            .iter()
            .copied()
            .filter(|&r| {
                let c = &self.slab[r as usize];
                c.alive && mask[c.y * self.width + c.x]
            })
            .collect()
    }

    /// `play._finish_edit`: refresh the terrain caches if the terrain changed, drop dead cells, recompute light.
    fn finish_edit(&mut self, terrain_changed: bool) {
        if terrain_changed {
            self.refresh_terrain();
        }
        let order = std::mem::take(&mut self.order);
        let mut kept = Vec::with_capacity(order.len());
        for r in order {
            if self.slab[r as usize].alive {
                kept.push(r);
            } else {
                self.free_slots.push(r);
            }
        }
        self.order = kept;
        self.update_light(self.step_count); // `world.now` equals `step_count` between steps
    }

    fn add_nutrients(&mut self, x: u32, y: u32, r: u32, amount: f64) -> u64 {
        let mask = self.disc(x, y, r);
        let mut changed = 0;
        for (i, &m) in mask.iter().enumerate() {
            if m && !self.terrain.rock[i] {
                self.organic[i] += amount;
                changed += 1;
            }
        }
        self.finish_edit(false);
        changed
    }

    fn meteorite(&mut self, x: u32, y: u32, r: u32) -> u64 {
        let mask = self.disc(x, y, r);
        let hit = self.cells_on(&mask);
        let (decomp, body) = (self.cfg.decomp_fraction, self.cfg.body_cost);
        for &c in &hit {
            let organic = decomp * (py_max(self.slab[c as usize].energy, 0.0) + body);
            self.kill(c, organic);
        }
        self.finish_edit(false);
        hit.len() as u64
    }

    fn raise_rock(&mut self, x: u32, y: u32, r: u32) -> u64 {
        let mut mask = self.disc(x, y, r);
        for (m, &rock) in mask.iter_mut().zip(&self.terrain.rock) {
            *m &= !rock;
        }
        let changed = mask.iter().filter(|&&m| m).count() as u64;
        if changed == 0 {
            return 0; // already rock: nothing to do (no refresh, light untouched)
        }
        for c in self.cells_on(&mask) {
            self.kill(c, 0.0);
        }
        for (i, &m) in mask.iter().enumerate() {
            if m {
                self.terrain.rock[i] = true;
                self.terrain.chem[i] = 0.0;
                self.organic[i] = 0.0; // nothing stays buried in rock
            }
        }
        self.finish_edit(true);
        changed
    }

    fn dig(&mut self, x: u32, y: u32, r: u32) -> u64 {
        let mask = self.disc(x, y, r);
        let mut changed = 0;
        for (i, &m) in mask.iter().enumerate() {
            if m && self.terrain.rock[i] {
                self.terrain.rock[i] = false;
                changed += 1;
            }
        }
        self.finish_edit(true); // always, as Python does
        changed
    }

    fn add_vent(&mut self, x: u32, y: u32, max_chem: f64) -> u64 {
        let (w, h) = (self.width, self.height);
        let (x, y) = (x as usize, y as usize);
        if self.terrain.rock[y * w + x] {
            return 0; // on rock: nothing happens (no refresh, light untouched)
        }
        let plume = vent_plume(h, w, x, y, self.cfg.vent_strength, self.cfg.vent_radius);
        // added = np.minimum(chem + plume, max_chem); chem = np.maximum(chem, added); chem[rock] = 0
        // (no NaN: inputs are validated, so plain comparisons equal numpy's)
        for (i, chem) in self.terrain.chem.iter_mut().enumerate() {
            let stacked = *chem + plume[i];
            let added = if stacked <= max_chem {
                stacked
            } else {
                max_chem
            };
            if added > *chem {
                *chem = added;
            }
            if self.terrain.rock[i] {
                *chem = 0.0;
            }
        }
        self.finish_edit(true);
        1
    }
}
