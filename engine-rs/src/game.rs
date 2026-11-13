//! ADR-0017: the G1 game rules of `worldsim/play.py` (`GameRules`, `Game`), ported as written, quirks included.
//!
//! A [`Game`] holds only the game's own state (budget, milestones, player vents, cataclysm tracking). It never
//! owns the world: every call takes the [`World`] it plays on, so a front-end can keep one world handle and attach
//! a game to it (piece 3). The rules draw nothing from the RNG and change nothing in how the world steps, so a
//! game with no actions leaves every state hash equal to the world stepped alone.
//!
//! Not here (Decision 3): the action log, restart and saving a game.

use std::collections::{BTreeSet, VecDeque};

use crate::world::{CellRef, Intervention, InterventionError, World};

/// Feeding share above which a cell counts as a specialist (`play.SPECIALIST`).
pub const SPECIALIST: f64 = 0.6;

/// Largest float a rule may hold (budget, regen, costs, amounts, radius and fractions): far above any game value,
/// far below where sums could overflow or lose integer precision in the counts they are compared with.
pub const MAX_RULE_VALUE: f64 = 1e12;

/// Largest tool radius: the side of the largest world (`MAX_WORLD_TILES` tiles in one row). A larger disc covers
/// no more tiles.
pub const MAX_RULE_RADIUS: u32 = 1_000_000;

/// The player's tools, in `play.TOOLS` order (the index is the ABI code minus one).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tool {
    Nutrients,
    Meteorite,
    Mountain,
    Dig,
    Volcano,
}

impl Tool {
    pub const ALL: [Tool; 5] = [
        Tool::Nutrients,
        Tool::Meteorite,
        Tool::Mountain,
        Tool::Dig,
        Tool::Volcano,
    ];

    /// The name `play.TOOLS` uses.
    pub fn name(self) -> &'static str {
        match self {
            Tool::Nutrients => "nutrients",
            Tool::Meteorite => "meteorite",
            Tool::Mountain => "mountain",
            Tool::Dig => "dig",
            Tool::Volcano => "volcano",
        }
    }

    /// The tool `play.TOOLS` names `name`.
    pub fn from_name(name: &str) -> Option<Tool> {
        Tool::ALL.into_iter().find(|t| t.name() == name)
    }

    fn index(self) -> usize {
        self as usize
    }
}

/// The milestones, in `play.MILESTONES` order. Their texts stay in the front-end (Decision 4).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Milestone {
    Abyss,
    Balance,
    Giant,
    Survivor,
    Divided,
}

impl Milestone {
    pub const ALL: [Milestone; 5] = [
        Milestone::Abyss,
        Milestone::Balance,
        Milestone::Giant,
        Milestone::Survivor,
        Milestone::Divided,
    ];

    /// The key `play.MILESTONES` uses.
    pub fn name(self) -> &'static str {
        match self {
            Milestone::Abyss => "abyss",
            Milestone::Balance => "balance",
            Milestone::Giant => "giant",
            Milestone::Survivor => "survivor",
            Milestone::Divided => "divided",
        }
    }
}

/// `play.GameRules`: per-tool values in [`Tool::ALL`] order. Untrusted when it comes through the ABI, so
/// [`GameRules::validate`] bounds every field before a [`Game`] uses it.
#[derive(Debug, Clone, PartialEq)]
pub struct GameRules {
    pub budget_max: f64,
    pub budget_start: f64,
    /// Divine energy per step.
    pub regen: f64,
    pub cost: [f64; 5],
    pub radius: [u32; 5],
    /// Organic matter added per tile by the nutrients tool.
    pub nutrients_amount: f64,
    /// Cap on stacked vent energy per tile.
    pub max_chem: f64,
    /// Steps between milestone checks (a modulus: at least 1).
    pub check_every: u64,
    /// Chemosynthesis specialists near a player vent.
    pub abyss_cells: u64,
    pub abyss_radius: f64,
    /// Specialists of each of the four strategies, at once.
    pub balance_cells: u64,
    /// Cells in one bonded colony.
    pub giant_colony: u64,
    /// Meteorites must kill this share of all life ...
    pub kill_fraction: f64,
    /// ... within this many steps of the first strike ...
    pub collapse_window: u64,
    /// ... then the smoothed population climbs back to this times its pre-strike value.
    pub recover_fraction: f64,
    /// Cells in each of two isolated seas.
    pub divided_cells: u64,
}

impl Default for GameRules {
    /// `GameRules()`; `golden_games.rs` keeps it equal to Python's defaults.
    fn default() -> Self {
        Self {
            budget_max: 100.0,
            budget_start: 100.0,
            regen: 0.05,
            cost: [10.0, 20.0, 4.0, 4.0, 40.0],
            radius: [6, 10, 2, 2, 0],
            nutrients_amount: 15.0,
            max_chem: 4.0,
            check_every: 25,
            abyss_cells: 50,
            abyss_radius: 6.0,
            balance_cells: 30,
            giant_colony: 80,
            kill_fraction: 1.0 / 3.0,
            collapse_window: 100,
            recover_fraction: 1.0,
            divided_cells: 100,
        }
    }
}

/// Rules a game refuses; the message names the field.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GameRulesError(String);

impl GameRulesError {
    pub fn message(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Display for GameRulesError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for GameRulesError {}

impl GameRules {
    /// Every float finite and in `[0, MAX_RULE_VALUE]` (`-0.0` refused too), every radius at most
    /// [`MAX_RULE_RADIUS`], `check_every >= 1`, and `nutrients_amount` within what an edit may add.
    pub fn validate(&self) -> Result<(), GameRulesError> {
        let mut floats = vec![
            ("budget_max", self.budget_max),
            ("budget_start", self.budget_start),
            ("regen", self.regen),
            ("nutrients_amount", self.nutrients_amount),
            ("max_chem", self.max_chem),
            ("abyss_radius", self.abyss_radius),
            ("kill_fraction", self.kill_fraction),
            ("recover_fraction", self.recover_fraction),
        ];
        let cost_names: Vec<String> = Tool::ALL
            .iter()
            .map(|t| format!("cost[{}]", t.name()))
            .collect();
        for (name, &v) in cost_names.iter().zip(&self.cost) {
            floats.push((name.as_str(), v));
        }
        for (name, v) in floats {
            if !(v.is_finite() && !v.is_sign_negative() && v <= MAX_RULE_VALUE) {
                return Err(GameRulesError(format!(
                    "{name} must be finite and in [0, {MAX_RULE_VALUE}], got {v}"
                )));
            }
        }
        for (t, &r) in Tool::ALL.iter().zip(&self.radius) {
            if r > MAX_RULE_RADIUS {
                return Err(GameRulesError(format!(
                    "radius[{}] must be at most {MAX_RULE_RADIUS}, got {r}",
                    t.name()
                )));
            }
        }
        if self.check_every == 0 {
            return Err(GameRulesError("check_every must be at least 1".into()));
        }
        Ok(())
    }
}

/// The current meteor strike (`Game._strike`).
#[derive(Debug, Clone)]
struct Strike {
    step: u64,
    pop: u64,
    smooth: f64,
    killed: u64,
    extinctions: u64,
    dipped: bool,
}

/// `play.Game` without its world: see the module documentation.
#[derive(Debug, Clone)]
pub struct Game {
    rules: GameRules,
    budget: f64,
    achieved: [Option<u64>; 5],
    /// Tiles of the vents the player opened, deduplicated (Decision 3: duplicates are count-neutral in Python).
    player_vents: BTreeSet<(usize, usize)>,
    /// Population after each step, at most `smooth_len` of them, grown as steps run (never preallocated).
    smooth: VecDeque<u32>,
    smooth_sum: u64,
    smooth_len: usize,
    strike: Option<Strike>,
    collapsed_from: Option<f64>,
    /// Cached sea labels and count; reset when rock changes.
    seas: Option<(Vec<u32>, u32)>,
}

/// What the milestone checks measure now, whatever has been reached already: the numbers a front-end can show
/// as progress, and the trace `golden_games.rs` compares at every check.
#[derive(Debug, Clone, PartialEq)]
pub struct Measures {
    /// Chemosynthesis specialists within `abyss_radius` of a player vent.
    pub near_vents: u64,
    /// Photosynthesis, decomposition and predation specialists.
    pub specialists: [u64; 3],
    /// Cells in the largest bonded colony.
    pub largest_colony: u64,
    /// Living cells per sea, in label order; empty when the world has no rock.
    pub cells_per_sea: Vec<u64>,
    /// The day-smoothed population.
    pub smoothed: f64,
    /// The smoothed population to recover to after a cataclysm, once one happened.
    pub collapse_target: Option<f64>,
    /// The smoothed population has dipped below that target since.
    pub dipped: bool,
}

/// Label of a rock tile in the sea labels.
const NO_SEA: u32 = u32::MAX;

impl Game {
    /// `Game(world, rules)`: validates the rules; the smoothing window spans one day when days are on.
    pub fn new(world: &World, rules: GameRules) -> Result<Self, GameRulesError> {
        rules.validate()?;
        let cfg = &world.cfg;
        // deque(maxlen=max(1, cfg.day_length if cfg.day_amplitude else 1)); day_length is bounded to 10^9
        let day = if cfg.day_amplitude != 0.0 {
            cfg.day_length
        } else {
            1
        };
        let smooth_len = usize::try_from(day.max(1)).unwrap_or(usize::MAX);
        Ok(Self {
            budget: rules.budget_start,
            rules,
            achieved: [None; 5],
            player_vents: BTreeSet::new(),
            smooth: VecDeque::new(),
            smooth_sum: 0,
            smooth_len,
            strike: None,
            collapsed_from: None,
            seas: None,
        })
    }

    pub fn rules(&self) -> &GameRules {
        &self.rules
    }

    pub fn budget(&self) -> f64 {
        self.budget
    }

    /// The step at which `m` was reached, if it was.
    pub fn achieved(&self, m: Milestone) -> Option<u64> {
        self.achieved[m as usize]
    }

    /// Distinct tiles of the vents the player opened.
    pub fn player_vents(&self) -> usize {
        self.player_vents.len()
    }

    pub fn can_afford(&self, tool: Tool) -> bool {
        self.budget >= self.rules.cost[tool.index()]
    }

    /// `Game.act`: apply `tool` at `(x, y)` if affordable. `Ok(true)` when something happened (and was paid for),
    /// `Ok(false)` when the action was refused (off the world, too expensive, or nothing to change). `Err` only
    /// when the kernel refuses the edit where Python has no bound (organic matter above `MAX_EDIT_ORGANIC`): the
    /// world and the game are then unchanged.
    pub fn act(
        &mut self,
        world: &mut World,
        tool: Tool,
        x: u32,
        y: u32,
    ) -> Result<bool, InterventionError> {
        if x as usize >= world.width || y as usize >= world.height || !self.can_afford(tool) {
            return Ok(false);
        }
        let r = self.rules.radius[tool.index()];
        let done = match tool {
            Tool::Nutrients => world.intervene(Intervention::Nutrients {
                x,
                y,
                radius: r,
                amount: self.rules.nutrients_amount,
            })?,
            Tool::Meteorite => {
                let pop_before = world.population() as u64;
                let killed = world.intervene(Intervention::Meteorite { x, y, radius: r })?;
                self.on_strike(world, pop_before, killed);
                1 // a strike on empty water still costs
            }
            Tool::Mountain => {
                let changed = world.intervene(Intervention::RaiseRock { x, y, radius: r })?;
                self.seas = None;
                changed
            }
            Tool::Dig => {
                let changed = world.intervene(Intervention::Dig { x, y, radius: r })?;
                self.seas = None;
                changed
            }
            Tool::Volcano => {
                let opened = world.intervene(Intervention::Vent {
                    x,
                    y,
                    max_chem: self.rules.max_chem,
                })?;
                if opened != 0 {
                    self.player_vents.insert((x as usize, y as usize));
                }
                opened
            }
        };
        if done == 0 {
            return Ok(false);
        }
        self.budget -= self.rules.cost[tool.index()];
        Ok(true)
    }

    /// `Game.step`: the world step, the budget regeneration, the smoothed-population sample, the cataclysm
    /// tracking and, every `check_every` steps, the milestone check.
    pub fn step(&mut self, world: &mut World) {
        world.step();
        let refilled = self.budget + self.rules.regen;
        // min(budget_max, refilled): Python returns the first argument unless the second is smaller
        self.budget = if refilled < self.rules.budget_max {
            refilled
        } else {
            self.rules.budget_max
        };
        let pop = world.population() as u32; // at most MAX_WORLD_TILES
        self.smooth.push_back(pop);
        self.smooth_sum += u64::from(pop);
        if self.smooth.len() > self.smooth_len {
            let old = self.smooth.pop_front().expect("window is not empty");
            self.smooth_sum -= u64::from(old);
        }
        self.track_cataclysm(world);
        if world.step_count.is_multiple_of(self.rules.check_every) {
            self.check_milestones(world);
        }
    }

    /// `Game._smoothed`: the window's mean (an exact integer sum, one division), or the population when empty.
    fn smoothed(&self, world: &World) -> f64 {
        if self.smooth.is_empty() {
            world.population() as f64
        } else {
            self.smooth_sum as f64 / self.smooth.len() as f64
        }
    }

    /// `Game._on_strike`: a cataclysm is meteorites killing `kill_fraction` of life within `collapse_window`
    /// steps. After a collapse a strike opens a new record but keeps the collapse target (Decision 4).
    fn on_strike(&mut self, world: &World, pop_before: u64, killed: u64) {
        let renew = match &self.strike {
            None => true,
            Some(s) => {
                self.collapsed_from.is_some()
                    || world.step_count.saturating_sub(s.step) > self.rules.collapse_window
            }
        };
        if renew {
            self.strike = Some(Strike {
                step: world.step_count,
                pop: pop_before,
                smooth: self.smoothed(world),
                killed: 0,
                extinctions: world.counters.extinctions,
                dipped: false,
            });
        }
        let s = self.strike.as_mut().expect("a strike record exists");
        s.killed += killed;
        if s.killed as f64 >= self.rules.kill_fraction * s.pop as f64
            && self.collapsed_from.is_none()
        {
            // recover to the pre-strike daily average (day/night swings make single counts noisy)
            self.collapsed_from = Some(s.smooth);
        }
    }

    /// `Game._track_cataclysm`.
    fn track_cataclysm(&mut self, world: &World) {
        if self.achieved(Milestone::Survivor).is_some() {
            return;
        }
        let (Some(s), Some(from)) = (&self.strike, self.collapsed_from) else {
            return;
        };
        if world.counters.extinctions != s.extinctions {
            // wiped out and reseeded: nobody survived
            self.strike = None;
            self.collapsed_from = None;
            return;
        }
        let target = self.rules.recover_fraction * from;
        let below = self.smoothed(world) < target;
        let s = self.strike.as_mut().expect("checked above");
        if below {
            s.dipped = true; // the lagging average must first feel the loss ...
        } else if s.dipped {
            self.reach(world, Milestone::Survivor); // ... and then climb back
        }
    }

    fn reach(&mut self, world: &World, m: Milestone) {
        let slot = &mut self.achieved[m as usize];
        if slot.is_none() {
            *slot = Some(world.step_count);
        }
    }

    /// `Game._chemo_near_player_vents`: chemosynthesis specialists within `abyss_radius` of a player vent. The
    /// distance is `sqrt` of an exact integer sum (Decision 5), equal to Python's `math.hypot` on these offsets.
    fn chemo_near_player_vents(&self, world: &World) -> u64 {
        let w = world.width;
        let radius = self.rules.abyss_radius;
        let mut near = 0;
        for c in world.cells() {
            if c.pheno.chemo >= SPECIALIST {
                let close = self.player_vents.iter().any(|&(vx, vy)| {
                    let d = c.x.abs_diff(vx);
                    let dx = d.min(w - d) as u64;
                    let dy = c.y.abs_diff(vy) as u64;
                    ((dx * dx + dy * dy) as f64).sqrt() <= radius
                });
                if close {
                    near += 1;
                }
            }
        }
        near
    }

    /// What the milestone checks measure now (see [`Measures`]). Labels the seas afresh: not for every frame.
    pub fn measures(&self, world: &World) -> Measures {
        let cells_per_sea = if world.has_rock {
            let (labels, n) = seas(world);
            cells_per_sea(world, &labels, n)
        } else {
            Vec::new()
        };
        Measures {
            near_vents: self.chemo_near_player_vents(world),
            specialists: specialists(world),
            largest_colony: largest_colony(world) as u64,
            cells_per_sea,
            smoothed: self.smoothed(world),
            collapse_target: self.collapsed_from,
            dipped: self.strike.as_ref().is_some_and(|s| s.dipped),
        }
    }

    /// `Game.check_milestones`.
    pub fn check_milestones(&mut self, world: &World) {
        let r = &self.rules;
        let (abyss, balance) = (
            self.achieved(Milestone::Abyss).is_some(),
            self.achieved(Milestone::Balance).is_some(),
        );
        let need_vents = (!abyss || !balance) && !self.player_vents.is_empty();
        let near = if need_vents {
            self.chemo_near_player_vents(world)
        } else {
            0
        };
        let (abyss_cells, balance_cells) = (r.abyss_cells, r.balance_cells);
        let (giant_colony, divided_cells) = (r.giant_colony, r.divided_cells);
        if !abyss && near >= abyss_cells {
            self.reach(world, Milestone::Abyss);
        }
        // chemosynthesizers count only around vents the player opened: planets with natural vents otherwise
        // reach a full ecosystem on their own
        if !balance
            && near >= balance_cells
            && specialists(world).iter().all(|&n| n >= balance_cells)
        {
            self.reach(world, Milestone::Balance);
        }
        if self.achieved(Milestone::Giant).is_none() && largest_colony(world) as u64 >= giant_colony
        {
            self.reach(world, Milestone::Giant);
        }
        if self.achieved(Milestone::Divided).is_none() && world.has_rock {
            let (labels, n) = self.seas.get_or_insert_with(|| seas(world));
            let alive_seas = if *n >= 2 {
                cells_per_sea(world, labels, *n)
                    .iter()
                    .filter(|&&k| k >= divided_cells)
                    .count()
            } else {
                0
            };
            if alive_seas >= 2 {
                self.reach(world, Milestone::Divided);
            }
        }
    }
}

/// Living cells that specialise in photosynthesis, decomposition and predation (share >= [`SPECIALIST`]).
fn specialists(world: &World) -> [u64; 3] {
    let mut counts = [0u64; 3];
    for c in world.cells() {
        let p = &c.pheno;
        for (n, share) in counts.iter_mut().zip([p.photo, p.sapro, p.pred]) {
            *n += u64::from(share >= SPECIALIST);
        }
    }
    counts
}

/// Living cells in each sea, by label (`np.bincount(..., minlength=n)`).
fn cells_per_sea(world: &World, labels: &[u32], n: u32) -> Vec<u64> {
    let mut per_sea = vec![0u64; n as usize];
    for c in world.cells() {
        per_sea[labels[c.y * world.width + c.x] as usize] += 1;
    }
    per_sea
}

/// `max(play.colony_sizes(cells), default=0)`: the largest bonded component among living cells.
fn largest_colony(world: &World) -> usize {
    let mut seen = vec![false; world.slab.len()];
    let mut stack: Vec<CellRef> = Vec::new();
    let mut largest = 0;
    for &start in &world.order {
        if world.slab[start as usize].bonds.is_empty() || seen[start as usize] {
            continue;
        }
        seen[start as usize] = true;
        stack.push(start);
        let mut n = 0;
        while let Some(cur) = stack.pop() {
            n += 1;
            for &b in &world.slab[cur as usize].bonds {
                if !seen[b as usize] {
                    seen[b as usize] = true;
                    stack.push(b);
                }
            }
        }
        largest = largest.max(n);
    }
    largest
}

/// `play.seas`: connected water regions (4-neighbour, toroidal in x), labelled in scan order. Rock is
/// [`NO_SEA`]. Returns the labels (row-major) and their count.
fn seas(world: &World) -> (Vec<u32>, u32) {
    let (w, h) = (world.width, world.height);
    let rock = &world.terrain.rock;
    let mut labels = vec![NO_SEA; w * h];
    let mut n = 0u32;
    let mut stack = Vec::new();
    for start in 0..w * h {
        if rock[start] || labels[start] != NO_SEA {
            continue;
        }
        labels[start] = n;
        stack.push(start);
        while let Some(i) = stack.pop() {
            let (x, y) = (i % w, i / w);
            let mut visit = |j: usize| {
                if !rock[j] && labels[j] == NO_SEA {
                    labels[j] = n;
                    stack.push(j);
                }
            };
            visit(y * w + (x + w - 1) % w);
            visit(y * w + (x + 1) % w);
            if y > 0 {
                visit(i - w);
            }
            if y + 1 < h {
                visit(i + w);
            }
        }
        n += 1;
    }
    (labels, n)
}
