"""G1 game rules: player interventions, a divine-energy budget and milestones.

Headless and deterministic. Interventions are instant edits of state that saves
already contain (cells, organic matter, terrain maps) and draw nothing from the
RNG, so the same seed plus the same actions at the same steps gives the same
history. Game rules (`GameRules`) never change how the simulation itself works,
which is why they live here and not in `Config`.

Milestones are chosen so an idle player does not reach them on the example
planets (measured 2026-11-10, 6000 steps): each needs one of the player's verbs.
"""
import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from .terrain import Terrain

TOOLS = ("nutrients", "meteorite", "mountain", "dig", "volcano")
SPECIALIST = 0.6          # feeding share above which a cell counts as a specialist


@dataclass
class GameRules:
    budget_max: float = 100.0
    budget_start: float = 100.0
    regen: float = 0.05                      # divine energy per step
    cost: dict = field(default_factory=lambda: {
        "nutrients": 10.0, "meteorite": 20.0, "mountain": 4.0, "dig": 4.0, "volcano": 40.0})
    radius: dict = field(default_factory=lambda: {
        "nutrients": 6, "meteorite": 10, "mountain": 2, "dig": 2, "volcano": 0})
    nutrients_amount: float = 15.0           # organic matter added per tile
    max_chem: float = 4.0                    # cap on stacked vent energy per tile
    check_every: int = 25                    # steps between milestone checks
    # milestone thresholds
    abyss_cells: int = 50                    # chemo specialists near a player vent
    abyss_radius: float = 6.0
    balance_cells: int = 30                  # specialists of each of the 4 strategies, at once
    giant_colony: int = 80                   # cells in one bonded colony (idle max seen: 55)
    kill_fraction: float = 1 / 3             # meteorites must kill this share of all life ...
    collapse_window: int = 100               # ... within this many steps of the first strike
    recover_fraction: float = 1.0            # then the smoothed population climbs back to this x before
    divided_cells: int = 100                 # cells in each of two isolated seas


MILESTONES = {
    "abyss": "Life in the abyss: a vent you made is colonised by chemosynthesizers",
    "balance": "Full ecosystem: plants, decomposers, predators and chemosynthesizers thrive together",
    "giant": "Giant organism: one colony of 80 cells",
    "survivor": "Survivors: life recovers from a cataclysm you caused",
    "divided": "Divided ocean: two isolated seas, both alive",
}


# ------------------------------------------------------------------ interventions
def _disc(world, x, y, r):
    """Boolean (H, W) mask of tiles within distance r of (x, y); toroidal in x."""
    H, W = world.H, world.W
    ys, xs = np.mgrid[0:H, 0:W]
    dx = np.abs(xs - x)
    dx = np.minimum(dx, W - dx)
    return dx * dx + (ys - y) ** 2 <= r * r


def _finish_edit(world, terrain_changed):
    if terrain_changed:
        world.set_terrain(world.terrain)          # rebuild blocked, base_light, sink mask, flags
    world.cells = [c for c in world.cells if c.alive]   # no ghosts outside step() either
    world.update_light()                          # a paused player sees the effect at once


def add_nutrients(world, x, y, r, amount):
    mask = _disc(world, x, y, r) & ~world.terrain.rock
    world.organic[mask] += amount
    _finish_edit(world, False)
    return int(mask.sum())


def meteorite(world, x, y, r):
    """Kill every cell in the impact disc; bodies become organic matter as usual."""
    mask = _disc(world, x, y, r)
    hit = [c for c in world.cells if c.alive and mask[c.y, c.x]]
    for c in hit:
        world.kill(c, world.cfg.decomp_fraction * (max(c.energy, 0.0) + world.cfg.body_cost))
    _finish_edit(world, False)
    return len(hit)


def raise_rock(world, x, y, r):
    """Rock rises in the disc: cells there are crushed and their energy is lost into the rock."""
    t = world.terrain
    mask = _disc(world, x, y, r) & ~t.rock
    if not mask.any():
        return 0                                  # already rock: nothing to do, nothing to pay
    for c in [c for c in world.cells if c.alive and mask[c.y, c.x]]:
        world.kill(c, 0.0)
    t.rock |= mask
    t.chem[mask] = 0.0
    world.organic[mask] = 0.0                     # nothing stays buried in rock
    _finish_edit(world, True)
    return int(mask.sum())


def dig(world, x, y, r):
    mask = _disc(world, x, y, r) & world.terrain.rock
    world.terrain.rock &= ~mask
    _finish_edit(world, True)
    return int(mask.sum())


def add_vent(world, x, y, max_chem):
    """A new hydrothermal vent at (x, y), shaped like the procedural ones."""
    cfg, t = world.cfg, world.terrain
    if t.rock[y, x]:
        return 0
    H, W = world.H, world.W
    ys, xs = np.mgrid[0:H, 0:W]
    dx = np.abs(xs - x)
    dx = np.minimum(dx, W - dx)
    added = np.minimum(t.chem + cfg.vent_strength * np.exp(-np.hypot(dx, ys - y) / cfg.vent_radius), max_chem)
    t.chem = np.maximum(t.chem, added)
    t.chem[t.rock] = 0.0
    _finish_edit(world, True)
    return 1


# ------------------------------------------------------------------ measurements
def colony_sizes(cells):
    """Sizes of the bonded components (colonies) among living cells."""
    seen, sizes = set(), []
    for c in cells:
        if not c.bonds or c.id in seen:
            continue
        seen.add(c.id)
        stack, n = [c], 0
        while stack:
            cur = stack.pop()
            n += 1
            for b in cur.bonds:
                if b.id not in seen:
                    seen.add(b.id)
                    stack.append(b)
        sizes.append(n)
    return sizes


def seas(world):
    """Label connected water regions (4-neighbour, toroidal in x). Returns (labels, count)."""
    H, W = world.H, world.W
    rock = world.terrain.rock
    labels = np.full((H, W), -1, dtype=np.int64)
    n = 0
    for y0 in range(H):
        for x0 in range(W):
            if rock[y0, x0] or labels[y0, x0] >= 0:
                continue
            labels[y0, x0] = n
            stack = [(x0, y0)]
            while stack:
                x, y = stack.pop()
                for nx, ny in ((x - 1) % W, y), ((x + 1) % W, y), (x, y - 1), (x, y + 1):
                    if 0 <= ny < H and not rock[ny, nx] and labels[ny, nx] < 0:
                        labels[ny, nx] = n
                        stack.append((nx, ny))
            n += 1
    return labels, n


# ------------------------------------------------------------------ the game
class Game:
    def __init__(self, world, rules: GameRules | None = None):
        self.world = world
        self.rules = rules or GameRules()
        self.budget = self.rules.budget_start
        self.achieved: dict[str, int] = {}       # milestone -> step reached
        self.actions: list[tuple[int, str, int, int]] = []   # (step, tool, x, y) of the current life
        self.player_vents: list[tuple[int, int]] = []
        self.pristine = Terrain(world.terrain.rock.copy(), world.terrain.chem.copy(),
                                world.terrain.sun.copy(), world.organic.copy())
        cfg = world.cfg
        self._smooth = deque(maxlen=max(1, cfg.day_length if cfg.day_amplitude else 1))
        self._strike = None                      # current meteor strike (see _on_strike)
        self._collapsed_from = None              # smoothed population to recover to, once struck hard enough
        self.news: list[str] = []                # messages for the front-end, drained by it
        self._seas = None                        # cached (labels, count); reset when rock changes

    def can_afford(self, tool):
        return self.budget >= self.rules.cost[tool]

    def act(self, tool, x, y):
        """Apply a tool at (x, y) if affordable. Returns True when something happened."""
        if tool not in TOOLS:
            raise ValueError(f"unknown tool {tool!r}")
        w, r = self.world, self.rules
        if not (0 <= x < w.W and 0 <= y < w.H) or not self.can_afford(tool):
            return False
        rad = r.radius[tool]
        if tool == "nutrients":
            done = add_nutrients(w, x, y, rad, r.nutrients_amount)
        elif tool == "meteorite":
            pop_before = len(w.cells)
            killed = meteorite(w, x, y, rad)
            done = 1                                 # a strike on empty water still costs
            self._on_strike(pop_before, killed)
        elif tool == "mountain":
            done = raise_rock(w, x, y, rad)
            self._seas = None
        elif tool == "dig":
            done = dig(w, x, y, rad)
            self._seas = None
        else:
            done = add_vent(w, x, y, r.max_chem)
            if done:
                self.player_vents.append((x, y))
        if not done:
            return False
        self.budget -= r.cost[tool]
        self.actions.append((w.step_count, tool, x, y))
        return True

    def step(self):
        """Advance the world one step, regenerate the budget, check milestones."""
        self.world.step()
        self.budget = min(self.rules.budget_max, self.budget + self.rules.regen)
        self._smooth.append(len(self.world.cells))
        self._track_cataclysm()
        if self.world.step_count % self.rules.check_every == 0:
            self.check_milestones()

    def restart(self, seed):
        """New life on the original planet (player edits undone, progress kept)."""
        from .world import World
        t = self.pristine
        terrain = Terrain(t.rock.copy(), t.chem.copy(), t.sun.copy(), t.organic.copy())
        self.world = World(self.world.cfg, seed=seed, terrain=terrain)
        self.actions = []                         # the log replays the current life only
        self.player_vents = []
        self._seas = None
        self._strike = self._collapsed_from = None
        self._smooth.clear()

    # -------------------------------------------------------------- milestones
    def _smoothed(self):
        return sum(self._smooth) / len(self._smooth) if self._smooth else len(self.world.cells)

    def _on_strike(self, pop_before, killed):
        """A cataclysm = meteorites killing `kill_fraction` of life within `collapse_window` steps.
        Counting kills (not population dips) keeps it independent of day/night swings."""
        w, r = self.world, self.rules
        s = self._strike
        if s is None or self._collapsed_from is not None or w.step_count - s["step"] > r.collapse_window:
            s = self._strike = {"step": w.step_count, "pop": pop_before, "smooth": self._smoothed(),
                                "killed": 0, "extinctions": w.extinctions, "dipped": False}
        s["killed"] += killed
        if s["killed"] >= r.kill_fraction * s["pop"] and self._collapsed_from is None:
            # recover to the pre-strike daily average (day/night swings make single counts noisy)
            self._collapsed_from = s["smooth"]

    def _track_cataclysm(self):
        s = self._strike
        if s is None or self._collapsed_from is None or "survivor" in self.achieved:
            return
        if self.world.extinctions != s["extinctions"]:   # wiped out and reseeded: nobody survived
            self._strike = self._collapsed_from = None
            return
        target = self.rules.recover_fraction * self._collapsed_from
        if self._smoothed() < target:
            s["dipped"] = True                    # the lagging average must first feel the loss ...
        elif s["dipped"]:
            self._reach("survivor")              # ... and then climb back

    def _reach(self, key):
        if key not in self.achieved:
            self.achieved[key] = self.world.step_count
            self.news.append(MILESTONES[key])

    def check_milestones(self):
        w, r = self.world, self.rules
        cells = w.cells
        if "abyss" not in self.achieved and self.player_vents:
            near = 0
            for c in cells:
                if c.chemo >= SPECIALIST:
                    for vx, vy in self.player_vents:
                        dx = abs(c.x - vx)
                        if math.hypot(min(dx, w.W - dx), c.y - vy) <= r.abyss_radius:
                            near += 1
                            break
            if near >= r.abyss_cells:
                self._reach("abyss")
        if "balance" not in self.achieved:
            counts = [sum(1 for c in cells if getattr(c, a) >= SPECIALIST) for a in ("photo", "sapro", "pred", "chemo")]
            if min(counts) >= r.balance_cells:
                self._reach("balance")
        if "giant" not in self.achieved and max(colony_sizes(cells), default=0) >= r.giant_colony:
            self._reach("giant")
        if "divided" not in self.achieved and w.has_rock:
            if self._seas is None:
                self._seas = seas(w)
            labels, n = self._seas
            if n >= 2:
                per_sea = np.bincount([labels[c.y, c.x] for c in cells], minlength=n)
                if np.sum(per_sea >= r.divided_cells) >= 2:
                    self._reach("divided")


def replay(world, actions, steps, rules=None):
    """Re-run a recorded game: apply each (step, tool, x, y) when the world reaches that step."""
    game = Game(world, rules)
    pending = deque(sorted(actions, key=lambda a: a[0]))   # stable: same-step order kept
    while world.step_count < steps:
        while pending and pending[0][0] <= game.world.step_count:
            _, tool, x, y = pending.popleft()
            game.act(tool, x, y)
        game.step()
    return game
