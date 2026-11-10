"""Species tracking and evolutionary-activity statistics.

A *pure observer* of the simulation: it never draws from the world RNG and the
engine never reads anything it computes, so the same seed produces the same
history with tracking on or off (see ADR-0003).

Species definition (threshold speciation on a fixed founder genome):
- Seeded and immigrant cells found a new *root* species.
- A newborn joins its parent's species if the distance between its genome and
  that species' founder genome is below `species_threshold`; otherwise it
  founds a new species whose parent is the parent's species. The distance is
  Euclidean, rescaled to a 10-gene genome (ADR-0005), so the threshold keeps
  its per-gene meaning when genes are appended.

Evolutionary activity (a simplified version of Bedau & Packard's statistics):
- Each species accumulates `activity` = sum over steps of its population.
- A species becomes *established* when its activity first reaches
  `novelty_activity`. The count of established species born by speciation
  (immigrant/seed roots excluded) is the "novelty" signal.
- Limitation: there is no neutral shadow model, so `novelty_activity` is an
  arbitrary threshold, not a significance level.
"""
import math

ORIGIN_SEED = "seed"
ORIGIN_IMMIGRANT = "immigrant"
ORIGIN_SPECIATION = "speciation"
REFERENCE_GENES = 10          # genome length the threshold was calibrated on (F1/F2)


def genome_distance(a, b):
    """Euclidean distance rescaled to a `REFERENCE_GENES`-gene genome (ADR-0005)."""
    return math.dist(a, b) * math.sqrt(REFERENCE_GENES / len(a))


class Species:
    __slots__ = ("id", "parent", "origin", "founder_genes", "born", "extinct",
                 "count", "peak", "activity", "established", "children")

    def __init__(self, sid, parent, origin, founder_genes, born):
        self.id = sid
        self.parent = parent            # parent species id, or None for roots
        self.origin = origin
        self.founder_genes = list(founder_genes)
        self.born = born                # step of origin
        self.extinct = None             # step of extinction, None while extant
        self.count = 0                  # living members
        self.peak = 0
        self.activity = 0               # cumulative population-steps
        self.established = None         # step when activity reached the threshold
        self.children = 0               # retained child species

    def to_list(self):
        return [self.id, self.parent, self.origin, self.founder_genes, self.born, self.extinct,
                self.count, self.peak, self.activity, self.established, self.children]

    @classmethod
    def from_list(cls, row):
        s = cls(row[0], row[1], row[2], row[3], row[4])
        s.extinct, s.count, s.peak, s.activity, s.established, s.children = row[5:]
        return s


class SpeciesTracker:
    def __init__(self, threshold, novelty_activity, prune_peak):
        self.threshold = threshold
        self.novelty_activity = novelty_activity
        self.prune_peak = prune_peak
        self.species: dict[int, Species] = {}
        self.extant: dict[int, Species] = {}
        self.next_id = 0
        self.speciations = 0            # species born by speciation (cumulative)
        self.novelty = 0                # established speciation-born species (cumulative)
        self.pruned = 0

    # ---------------------------------------------------------------- events
    def _new_species(self, parent, origin, genes, step):
        self.next_id += 1
        s = Species(self.next_id, parent, origin, genes, step)
        self.species[s.id] = s
        self.extant[s.id] = s
        if parent is not None:
            self.species[parent].children += 1
        return s

    def _join(self, cell, s):
        cell.species = s.id
        s.count += 1
        if s.count > s.peak:
            s.peak = s.count

    def on_root(self, cell, origin, step):
        self._join(cell, self._new_species(None, origin, cell.genes, step))

    def on_birth(self, child, parent_cell, step):
        s = self.species[parent_cell.species]
        if genome_distance(child.genes, s.founder_genes) < self.threshold:
            self._join(child, s)
        else:
            self.speciations += 1
            self._join(child, self._new_species(s.id, ORIGIN_SPECIATION, child.genes, step))

    def on_death(self, cell, step):
        s = self.species[cell.species]
        s.count -= 1
        if s.count == 0:
            s.extinct = step
            del self.extant[s.id]
            self._maybe_prune(s)

    def end_step(self, step):
        thr = self.novelty_activity
        for s in self.extant.values():
            s.activity += s.count
            if s.established is None and s.activity >= thr:
                s.established = step
                if s.origin == ORIGIN_SPECIATION:
                    self.novelty += 1

    # --------------------------------------------------------------- pruning
    def _maybe_prune(self, s):
        """Forget extinct, childless, never-large species (mostly failed immigrants),
        cascading to ancestors that become prunable. Keeps memory bounded."""
        while (s is not None and s.extinct is not None and s.children == 0
               and s.peak < self.prune_peak and s.established is None):
            del self.species[s.id]
            self.pruned += 1
            parent = self.species.get(s.parent) if s.parent is not None else None
            if parent is not None:
                parent.children -= 1
            s = parent

    # ----------------------------------------------------------------- stats
    def stats(self):
        n = len(self.extant)
        return {
            "species": n,
            "speciations": self.speciations,
            "novelty": self.novelty,
            "mean_species_activity": round(sum(s.activity for s in self.extant.values()) / n, 1) if n else 0.0,
        }

    # ----------------------------------------------------------- persistence
    def to_dict(self):
        return {
            "threshold": self.threshold, "novelty_activity": self.novelty_activity,
            "prune_peak": self.prune_peak, "next_id": self.next_id,
            "speciations": self.speciations, "novelty": self.novelty, "pruned": self.pruned,
            "species": [s.to_list() for s in self.species.values()],
        }

    @classmethod
    def from_dict(cls, d):
        t = cls(d["threshold"], d["novelty_activity"], d["prune_peak"])
        t.next_id, t.speciations, t.novelty, t.pruned = d["next_id"], d["speciations"], d["novelty"], d["pruned"]
        for row in d["species"]:
            s = Species.from_list(row)
            t.species[s.id] = s
            if s.extinct is None:
                t.extant[s.id] = s
        return t
