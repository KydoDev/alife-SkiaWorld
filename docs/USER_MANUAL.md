# User Manual

Last updated: 2026-11-10 (F5a two parents)

WorldSim has three programs:

| Program | What it is for |
|---|---|
| `game.py` | **Planet in a jar**, the playable prototype: shape a planet and reach milestones |
| `view.py` | Watch a world evolve, inspect cells, with no goals or budget |
| `run.py` | Headless experiments: CSV statistics, snapshots, saves and charts |

Setup: Python 3.12+, then `./scripts/bootstrap-dev.ps1` (Windows) or
`./scripts/bootstrap-dev.sh`, or simply `pip install -r requirements.txt`.

---

## Planet in a jar (`game.py`)

```bash
python game.py                                    # the "Volcanic ocean" planet
python game.py --planet examples/red_dwarf.json   # another planet form
python game.py --planet my_photo.jpg              # a planet made from your photo
python game.py --set rock_fraction=0.3 --seed 7   # tweak any parameter
python game.py --load runs/a/world_final.json.gz  # play on a saved world
```

You are the planet. You cannot touch a cell's genes: life evolves on its own,
by mutation and implicit selection. You change the **world**, and life adapts.

### Divine energy
The gold bar at the top right. Each intervention costs energy; it regenerates
slowly (5 points every 100 steps, maximum 100). Greyed-out tools are too
expensive right now.

### Tools
| Key | Tool | Cost | Effect |
|---|---|---|---|
| 1 | Nutrients | 10 | Drops organic food in a disc (radius 6): feeds decomposers |
| 2 | Meteorite | 20 | Kills every cell in a disc (radius 10); bodies become food |
| 3 | Mountain | 4 | Raises rock (radius 2). Hold and drag to build a wall. Cells there are crushed; rock casts shadow |
| 4 | Dig | 4 | Removes rock (radius 2). Hold and drag |
| 5 | Volcano | 40 | Opens a hydrothermal vent: chemical energy in the dark, for chemosynthesizers |

Left click uses the selected tool; the white circle shows its reach.

### Milestones
| Milestone | How to get it |
|---|---|
| Life in the abyss | Open a vent with the volcano; wait until 50 chemosynthesis specialists live around it |
| Full ecosystem | At one moment, at least 30 specialists of each strategy: plants, decomposers, predators, and chemosynthesizers living around a vent **you** opened |
| Giant organism | One colony (cells bonded together) of 80 cells |
| Survivors | Kill a third of all life with meteorites within 100 steps, then let the population recover to its previous level. If life dies out completely it does not count |
| Divided ocean | Build walls so the ocean splits into two isolated seas, each with at least 100 cells (the ocean wraps around left-right, so you need two walls) |

None of them happens on its own: an idle player reaches none on the example
planets (measured). Milestones are kept when you restart with `R`.

Difficulty depends on the planet. On the default *Volcanic ocean* all five are
reachable (verified with scripted players; aim meteorites at crowded areas;
*Giant organism* is the slowest and may need more than 20 000 steps). On
flat or steady planets, *Giant organism* and *Full ecosystem* are much harder:
day/night cycles, seasons and several vents help diversity.

### Other controls
| Input | Action |
|---|---|
| Right click | Inspect a cell (strategy, energy, age, bonds), shown under the world |
| `SPACE` | Pause / resume (tools still work while paused) |
| `+` / `-` | Simulation speed |
| `O` | Show / hide organic matter |
| `R` | New life on the original planet (your edits are undone, milestones kept) |
| `ESC` | Quit |

The game is not saved yet (planned for G3). The panel's colour key explains
what you see; see also *Colours* below.

---

## Viewer (`view.py`)
```bash
python view.py                                    # default world
python view.py --planet examples/volcanic.json    # a planet form or image
python view.py --set day_amplitude=1 --set vent_count=4
python view.py --load runs/a/world_final.json.gz  # open a save
python view.py --set sensing=1                    # cells steer by their senses (F3)
python view.py --set sensing=1 --set open_genome=1  # cells evolve their own rules (F4)
python view.py --set sex=1                        # cells may recombine with a partner (F5a)
python view.py --set plasticity=1                 # cells adjust their diet during life (F5b)
python view.py --set hgt=1                        # cells copy genes from neighbours (F5c)
python view.py --set defence=1                    # prey can repel attacks with an armour (F5e)
```
Keys: `SPACE` pause · `N` one step while paused · `+/-` speed · `O` organic
matter · `S` snapshot PNG · `R` new seed on the same terrain · click to inspect
a cell (its genes; *sensor weights* from −1 = avoids to +1 = seeks light, organic matter,
chemical energy, kin, strangers, danger — they only act with `--set sensing=1`; with
`--set open_genome=1` also its first *rules*, e.g. `light<0.20 w_light +0.80` = "when it is
darker than 0.2 here, seek light more"; with `--set sex=1` its *mating propensity*, the chance
that it recombines with a similar cell nearby when it divides; with `--set plasticity=1` its
*plasticity*, how fast it shifts its diet towards the food found where it is — its colour can
change during its life; with `--set hgt=1` its *transfer propensity* (`hgt`), how often it copies
one gene from a neighbour during its life; with `--set defence=1` its *armour* (`armor`), the share of
attacks it can repel, which costs energy every step) · `ESC` quit.

## Unity front-end (preview, G2)
A first Unity front-end runs the world on the Rust kernel, which is much faster than Python and
gives the same result step for step. For now it only **shows** a world: it loads a save made by
the Python engine (default options, optionally with prey defence, gene transfer, plasticity, two parents
and/or sensing on) and offers play/pause, single step and speed (1–480
steps/s). Controls: the buttons on top, or `Space` play/pause, `N` one step (when paused), `+`/`-`
speed. Planets, interventions and the optional mechanisms arrive later; to play, use `game.py`.
Setup is in the Developer Guide (Unity front-end).

## Headless runs (`run.py`)
```bash
python run.py --steps 10000 --seed 1 --out runs/test1
python run.py --planet examples/volcanic.json --steps 5000 --out runs/v --save-every 1000
python run.py --resume runs/v/world_003000.json.gz --steps 2000 --out runs/v2
```
The output folder gets `stats.csv`, `stats.png`, `species_tree.png`,
`novelty.png`, `species.csv`, snapshots and saves (written at the end of a run).
Saves are tied to the genome format: a save from an older version (before the F5e
prey defence) is refused with a clear message, so re-run instead of resuming it.

## Colours
| Colour | Meaning |
|---|---|
| Green / purple / red / cyan cells | plants / decomposers / predators / chemosynthesizers; mixed colours = mixed diets |
| Brighter cells | members of a colony |
| Blue water | light (dark = depth or shade) |
| Brown | organic matter |
| Orange glow | chemical energy around vents |
| Grey | rock |

## Making a planet
A planet form is a small JSON file (see `examples/`):
`star` (`red_dwarf`, `sun`, `blue_giant`), `day_night` (0–1), `seasonality`
(0–0.9), `ocean_depth` (5–200), `seabed_relief` (0–0.6), `volcanism` (0–50
vents), `mineral_richness` (0–10), optional `seed`, `name`, and `config` with
any simulation parameter. A photo works too: bright columns get more sun, red
areas become mineral-rich, blue areas start with nutrients, strong edges
become rock walls. The same photo always gives the same planet. Planet files
from other people are safe to open: they are validated and never executed.
