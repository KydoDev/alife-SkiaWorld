//! The species tracker (`worldsim/species.py`, ADR-0003 / ADR-0018): a pure observer of the simulation.
//!
//! It never draws from the RNG and nothing in the step reads it, so a world steps to the same state hash with
//! tracking on or off. Seeded, reseeded and immigrant cells found a *root* species; a newborn joins its parent's
//! species when its genome is closer than `species_threshold` to that species' founder genome
//! ([`genome_distance`], rescaled per gene, ADR-0005), otherwise it founds a child species. Each step adds every
//! extant species' population to its activity; a species is *established* when its activity reaches
//! `novelty_activity` (the established speciation-born ones count as novelty). Extinct, childless, small,
//! never-established species are forgotten (pruned), cascading to their ancestors.
//!
//! Species ids start at 1; 0 means "no species" across the ABI. Species are kept in id order, which is Python's
//! dict order (ids only grow). Extant and extinct species live in two maps, so the per-step `end_step` walks the
//! extant ones without a lookup each (it was most of the tracker's cost).

use crate::world::genome_distance;
use crate::N_GENES;
use std::collections::BTreeMap;

/// How a species began (`species.ORIGIN_*`), in the order of their ABI codes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Origin {
    Seed,
    Immigrant,
    Speciation,
}

impl Origin {
    /// Every origin, in code order.
    pub const ALL: [Origin; 3] = [Origin::Seed, Origin::Immigrant, Origin::Speciation];

    /// Python's name of the origin.
    pub fn name(self) -> &'static str {
        match self {
            Origin::Seed => "seed",
            Origin::Immigrant => "immigrant",
            Origin::Speciation => "speciation",
        }
    }

    /// The origin named `name`, if any.
    pub fn from_name(name: &str) -> Option<Origin> {
        Origin::ALL.into_iter().find(|o| o.name() == name)
    }

    /// The ABI code: 0 seed, 1 immigrant, 2 speciation.
    pub fn code(self) -> u8 {
        self as u8
    }
}

/// One species (`species.Species`).
#[derive(Debug, Clone, PartialEq)]
pub struct Species {
    pub id: u64,
    /// The parent species (possibly pruned since), `None` for a root.
    pub parent: Option<u64>,
    pub origin: Origin,
    pub founder_genes: [f64; N_GENES],
    /// Step of origin.
    pub born: u64,
    /// Step of extinction, `None` while extant.
    pub extinct: Option<u64>,
    /// Living members.
    pub count: u64,
    pub peak: u64,
    /// Cumulative population-steps.
    pub activity: u64,
    /// Step when the activity first reached `novelty_activity`.
    pub established: Option<u64>,
    /// Retained child species.
    pub children: u64,
}

/// The tracker's parameters, from the config (`species_threshold`, `novelty_activity`, `species_prune_peak`).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct TrackerParams {
    pub threshold: f64,
    pub novelty_activity: u64,
    pub prune_peak: i64,
}

/// The cumulative counters of a tracker.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct TrackerCounters {
    /// The last species id given (ids start at 1).
    pub next_id: u64,
    /// Species born by speciation.
    pub speciations: u64,
    /// Established speciation-born species.
    pub novelty: u64,
    /// Species forgotten.
    pub pruned: u64,
}

/// `species.SpeciesTracker`.
#[derive(Debug, Clone, PartialEq)]
pub struct SpeciesTracker {
    params: TrackerParams,
    counters: TrackerCounters,
    /// The extant species, by id.
    extant: BTreeMap<u64, Species>,
    /// The retained extinct species, by id.
    extinct: BTreeMap<u64, Species>,
}

impl SpeciesTracker {
    /// An empty tracker.
    pub fn new(params: TrackerParams) -> Self {
        Self {
            params,
            counters: TrackerCounters::default(),
            extant: BTreeMap::new(),
            extinct: BTreeMap::new(),
        }
    }

    /// A tracker restored from a save, checked so that no later birth or death can fail: ids unique, in
    /// `1..=next_id`, parents older than their children, roots without a parent and speciations with one,
    /// `extinct` set exactly for species with no living member, `peak >= count`, and `children` equal to the
    /// retained species naming it as parent. The caller checks the counts against the living cells and the
    /// numeric bounds of every field. Errors are short messages.
    pub fn restore(
        params: TrackerParams,
        counters: TrackerCounters,
        rows: Vec<Species>,
    ) -> Result<Self, String> {
        let mut species = BTreeMap::new();
        for s in rows {
            if s.id == 0 || s.id > counters.next_id {
                return Err(format!(
                    "species id {} outside 1..={}",
                    s.id, counters.next_id
                ));
            }
            let genes_ok = s
                .founder_genes
                .iter()
                .all(|g| g.is_finite() && (0.0..=1.0).contains(g));
            if !genes_ok {
                return Err(format!("species #{} has an invalid founder genome", s.id));
            }
            let parent_ok = match (s.origin, s.parent) {
                (Origin::Speciation, Some(p)) => p != 0 && p < s.id,
                (Origin::Seed | Origin::Immigrant, None) => true,
                _ => false,
            };
            if !parent_ok {
                return Err(format!("species #{} has an invalid parent", s.id));
            }
            let alive_ok = (s.extinct.is_none()) == (s.count > 0) && s.peak >= s.count;
            if !alive_ok {
                return Err(format!(
                    "species #{} has an invalid count or extinction",
                    s.id
                ));
            }
            let id = s.id;
            if species.insert(id, s).is_some() {
                return Err(format!("duplicate species id {id}"));
            }
        }
        let mut children: BTreeMap<u64, u64> = BTreeMap::new();
        for s in species.values() {
            if let Some(p) = s.parent.filter(|p| species.contains_key(p)) {
                *children.entry(p).or_default() += 1;
            }
        }
        for s in species.values() {
            if s.children != children.get(&s.id).copied().unwrap_or(0) {
                return Err(format!("species #{} has a wrong number of children", s.id));
            }
        }
        let (extant, extinct) = species.into_iter().partition(|(_, s)| s.extinct.is_none());
        Ok(Self {
            params,
            counters,
            extant,
            extinct,
        })
    }

    pub fn params(&self) -> TrackerParams {
        self.params
    }

    pub fn counters(&self) -> TrackerCounters {
        self.counters
    }

    /// Every retained species, in id order.
    pub fn species(&self) -> Vec<&Species> {
        let mut all: Vec<&Species> = self.extant.values().chain(self.extinct.values()).collect();
        all.sort_unstable_by_key(|s| s.id);
        all
    }

    /// The extant species, in id order.
    pub fn extant(&self) -> impl Iterator<Item = &Species> {
        self.extant.values()
    }

    pub fn extant_count(&self) -> usize {
        self.extant.len()
    }

    pub fn retained_count(&self) -> usize {
        self.extant.len() + self.extinct.len()
    }

    /// A retained species (`None` if unknown or pruned).
    pub fn get(&self, id: u64) -> Option<&Species> {
        self.extant.get(&id).or_else(|| self.extinct.get(&id))
    }

    fn get_mut(&mut self, id: u64) -> Option<&mut Species> {
        match self.extant.get_mut(&id) {
            Some(s) => Some(s),
            None => self.extinct.get_mut(&id),
        }
    }

    // ------------------------------------------------------------------ events

    fn new_species(
        &mut self,
        parent: Option<u64>,
        origin: Origin,
        genes: &[f64; N_GENES],
        step: u64,
    ) -> u64 {
        self.counters.next_id += 1;
        let id = self.counters.next_id;
        if let Some(p) = parent.and_then(|p| self.get_mut(p)) {
            p.children += 1;
        }
        self.extant.insert(
            id,
            Species {
                id,
                parent,
                origin,
                founder_genes: *genes,
                born: step,
                extinct: None,
                count: 0,
                peak: 0,
                activity: 0,
                established: None,
                children: 0,
            },
        );
        id
    }

    fn join(&mut self, id: u64) -> u64 {
        let s = self.extant.get_mut(&id).expect("joining an extant species");
        s.count += 1;
        s.peak = s.peak.max(s.count);
        id
    }

    /// `on_root`: a seeded, reseeded or immigrant cell founds a species; returns its id (the cell's species).
    pub fn on_root(&mut self, genes: &[f64; N_GENES], origin: Origin, step: u64) -> u64 {
        let id = self.new_species(None, origin, genes, step);
        self.join(id)
    }

    /// `on_birth`: the species of a newborn with `genes` whose parent cell belongs to `parent_species`.
    pub fn on_birth(
        &mut self,
        child_genes: &[f64; N_GENES],
        parent_species: u64,
        step: u64,
    ) -> u64 {
        let founder = &self.extant[&parent_species].founder_genes;
        if genome_distance(child_genes, founder) < self.params.threshold {
            self.join(parent_species)
        } else {
            self.counters.speciations += 1;
            let id = self.new_species(Some(parent_species), Origin::Speciation, child_genes, step);
            self.join(id)
        }
    }

    /// `on_death`: a member of `species` died at `step`.
    pub fn on_death(&mut self, species: u64, step: u64) {
        let s = self
            .extant
            .get_mut(&species)
            .expect("a living cell's species is extant");
        s.count -= 1;
        if s.count == 0 {
            let mut s = self.extant.remove(&species).expect("just found");
            s.extinct = Some(step);
            self.extinct.insert(species, s);
            self.maybe_prune(species);
        }
    }

    /// `end_step`: activity and establishment, once per step.
    pub fn end_step(&mut self, step: u64) {
        let threshold = self.params.novelty_activity;
        for s in self.extant.values_mut() {
            s.activity = s.activity.saturating_add(s.count);
            if s.established.is_none() && s.activity >= threshold {
                s.established = Some(step);
                if s.origin == Origin::Speciation {
                    self.counters.novelty += 1;
                }
            }
        }
    }

    /// `_maybe_prune`: forget an extinct, childless, never-large, never-established species, then its parent if
    /// that becomes prunable, and so on.
    fn maybe_prune(&mut self, mut id: u64) {
        while let Some(s) = self.get(id) {
            let prunable = s.extinct.is_some()
                && s.children == 0
                && (s.peak as i64) < self.params.prune_peak
                && s.established.is_none();
            if !prunable {
                return;
            }
            let parent = s.parent;
            self.extinct.remove(&id); // prunable: extinct
            self.counters.pruned += 1;
            match parent.and_then(|p| self.get_mut(p)) {
                Some(p) => {
                    p.children -= 1;
                    id = p.id;
                }
                None => return,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn params() -> TrackerParams {
        TrackerParams {
            threshold: 0.3,
            novelty_activity: 10,
            prune_peak: 5,
        }
    }

    #[test]
    fn a_small_extinct_line_is_pruned_back_to_an_established_ancestor() {
        let mut t = SpeciesTracker::new(params());
        let root = t.on_root(&[0.0; N_GENES], Origin::Seed, 0);
        let child = t.on_birth(&[1.0; N_GENES], root, 1);
        assert_ne!(child, root);
        assert_eq!(t.get(root).unwrap().children, 1);
        let grandchild = t.on_birth(&[0.0; N_GENES], child, 2);
        assert_eq!(t.counters().speciations, 2);
        t.on_death(root, 3); // the root dies out, but it has a child: kept
        assert!(t.get(root).is_some());
        t.on_death(child, 4); // extinct, has a child: kept
        t.on_death(grandchild, 5); // pruned, then child, then root
        assert_eq!(t.retained_count(), 0);
        assert_eq!(t.counters().pruned, 3);
    }

    #[test]
    fn an_established_speciation_counts_as_novelty() {
        let mut t = SpeciesTracker::new(params());
        let root = t.on_root(&[0.0; N_GENES], Origin::Immigrant, 0);
        let child = t.on_birth(&[1.0; N_GENES], root, 1);
        for step in 1..=10 {
            t.end_step(step);
        }
        assert_eq!(t.get(child).unwrap().established, Some(10));
        assert_eq!(t.counters().novelty, 1, "the immigrant root does not count");
    }

    #[test]
    fn restore_refuses_inconsistent_species() {
        let mut t = SpeciesTracker::new(params());
        let root = t.on_root(&[0.5; N_GENES], Origin::Seed, 0);
        t.on_birth(&[1.0; N_GENES], root, 1);
        let rows: Vec<Species> = t.species().into_iter().cloned().collect();
        let ok = SpeciesTracker::restore(t.params(), t.counters(), rows.clone()).unwrap();
        assert_eq!(ok, t);
        let bad = |f: &dyn Fn(&mut Vec<Species>)| {
            let mut r = rows.clone();
            f(&mut r);
            SpeciesTracker::restore(t.params(), t.counters(), r).is_err()
        };
        assert!(bad(&|r| r[0].id = 0));
        assert!(bad(&|r| r[1].id = 99));
        assert!(bad(&|r| r[1].id = 1)); // duplicate
        assert!(bad(&|r| r[0].founder_genes[3] = f64::NAN));
        assert!(bad(&|r| r[0].parent = Some(2))); // a root with a parent
        assert!(bad(&|r| r[1].parent = None)); // a speciation without one
        assert!(bad(&|r| r[0].children = 0));
        assert!(bad(&|r| r[0].extinct = Some(1))); // extinct with a member
        assert!(bad(&|r| r[0].count = 0)); // no member, not extinct
        assert!(bad(&|r| r[0].peak = 0));
    }

    #[test]
    fn origin_names_and_codes() {
        for (code, o) in Origin::ALL.into_iter().enumerate() {
            assert_eq!(o.code() as usize, code);
            assert_eq!(Origin::from_name(o.name()), Some(o));
        }
        assert_eq!(Origin::from_name("other"), None);
    }
}
