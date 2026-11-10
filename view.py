"""Interactive viewer (pygame).

    python view.py [--seed 1] [--scale 6]
    python view.py --load runs/test1/world_final.json.gz
    python view.py --planet examples/volcanic.json      # or an image file
    python view.py --set rock_fraction=0.3 --set vent_count=6 --set day_amplitude=1

Controls:
  SPACE   pause / resume          N    one step (while paused)
  + / -   steps per frame         O    show/hide organic matter
  S       save PNG snapshot       R    restart (new seed, same terrain)
  click   inspect a cell          ESC  quit
"""
import argparse
import random

import numpy as np
import pygame

from worldsim import Config, World
from worldsim.persistence import load_world
from worldsim.render import LEGEND, render_rgb, save_png
from worldsim.worldgen import PlanetError, load_planet
from worldsim.world import GENE_NAMES

PANEL_W = 260
PANEL_TOP = 10
LINE_H = 18
# Tallest panel: 12 stat lines (incl. blank) + 4 cell-header lines (incl. blank) + one line per gene,
# then the colour legend (title + one line per entry + a note) below a blank line.
LEGEND_LINES = 2 + len(LEGEND) + 2
PANEL_MAX_LINES = 12 + 4 + len(GENE_NAMES) + LEGEND_LINES
SWATCH = 10


def add_world_args(p):
    """World-selection options shared by the viewer and the game."""
    p.add_argument("--seed", type=int, default=None, help="RNG seed (default 1; a planet has its own)")
    p.add_argument("--scale", type=int, default=6)
    p.add_argument("--load", metavar="SAVE", help="open a world_*.json.gz save file instead of a new world")
    p.add_argument("--planet", metavar="FILE", help="generate the world from a planet form (.json) or an image")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override a Config parameter (form fields win over --set with --planet)")


def create_world(args):
    if args.load:
        if args.set or args.planet or args.seed is not None:
            raise SystemExit("--load opens the saved world as-is: --set/--planet/--seed are not allowed")
        return load_world(args.load)
    else:
        try:
            base = Config().apply_overrides(args.set)
            if args.planet:
                cfg, terrain, seed = load_planet(args.planet, base, args.seed)
            else:
                cfg, terrain, seed = base.validate(), None, 1 if args.seed is None else args.seed
        except (PlanetError, ValueError) as e:
            raise SystemExit(f"Invalid world: {e}") from e
        world = World(cfg, seed=seed, terrain=terrain)
    return world


def main():
    p = argparse.ArgumentParser(description="WorldSim interactive viewer")
    add_world_args(p)
    args = p.parse_args()
    world = create_world(args)
    cfg = world.cfg
    sc = args.scale
    pygame.init()
    # The window must fit both the world and the full inspector panel, whichever is taller.
    height = max(cfg.height * sc, 2 * PANEL_TOP + PANEL_MAX_LINES * LINE_H)
    screen = pygame.display.set_mode((cfg.width * sc + PANEL_W, height))
    pygame.display.set_caption("WorldSim")
    font = pygame.font.SysFont("consolas", 15)
    clock = pygame.time.Clock()

    paused, steps_per_frame, show_org = False, 1, True
    selected = None
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_SPACE:
                    paused = not paused
                elif ev.key == pygame.K_n and paused:
                    world.step()
                elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    steps_per_frame = min(steps_per_frame * 2, 64)
                elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    steps_per_frame = max(steps_per_frame // 2, 1)
                elif ev.key == pygame.K_o:
                    show_org = not show_org
                elif ev.key == pygame.K_s:
                    name = f"snapshot_{world.step_count:06d}.png"
                    save_png(world, name)
                    print("Saved", name)
                elif ev.key == pygame.K_r:
                    world = World(cfg, seed=random.randrange(1_000_000), terrain=world.terrain)
                    selected = None
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                selected = world.cell_at(mx // sc, my // sc)

        if not paused:
            for _ in range(steps_per_frame):
                world.step()

        img = render_rgb(world, show_organic=show_org)
        surf = pygame.surfarray.make_surface(np.transpose(img, (1, 0, 2)))
        surf = pygame.transform.scale(surf, (cfg.width * sc, cfg.height * sc))
        screen.fill((18, 18, 24))
        screen.blit(surf, (0, 0))

        if selected is not None and selected.alive:
            pygame.draw.rect(screen, (255, 255, 255),
                             (selected.x * sc - 2, selected.y * sc - 2, sc + 4, sc + 4), 1)

        s = world.stats()
        lines = [
            f"step         {s['step']}",
            f"population   {s['population']}",
            f"    plants   {s['photo']}",
            f"    decomp.  {s['sapro']}",
            f"    predat.  {s['pred']}",
            f"    chemo    {s['chemo']}",
            f"in colony    {s['in_colony']}",
            f"lineages     {s['lineages']}",
            f"species      {s.get('species', '-')}",
            f"light        {s['light_factor']:.2f}",
            f"steps/frame  {steps_per_frame}{'  [PAUSED]' if paused else ''}",
            "",
        ]
        if selected is not None:
            if selected.alive:
                lines += [f"cell #{selected.id}", f"energy {selected.energy:.1f}  age {selected.age}",
                          f"bonds {len(selected.bonds)}  strategy {selected.strategy}", ""]
                lines += [f"{n:7s} {v:.2f}" for n, v in zip(GENE_NAMES, selected.genes)]
            else:
                lines.append("(dead cell)")
        else:
            lines.append("click a cell to inspect")
        x0 = cfg.width * sc + 12
        for i, t in enumerate(lines):
            screen.blit(font.render(t, True, (220, 220, 220)), (x0, PANEL_TOP + i * LINE_H))
        for i, (_, color) in enumerate(LEGEND[:4]):          # swatches next to the strategy counts
            draw_swatch(screen, color, x0 + 12, PANEL_TOP + (2 + i) * LINE_H)
        draw_legend(screen, font, x0, height - PANEL_TOP - LEGEND_LINES * LINE_H + LINE_H)

        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


def draw_swatch(screen, color, x, y):
    pygame.draw.rect(screen, tuple(int(c) for c in color), (x, y + (LINE_H - SWATCH) // 2 - 1, SWATCH, SWATCH))


def draw_legend(screen, font, x, y):
    """Colour key, pinned to the bottom of the panel."""
    screen.blit(font.render("colours", True, (150, 150, 160)), (x, y))
    for i, (label, color) in enumerate(LEGEND, start=1):
        draw_swatch(screen, color, x, y + i * LINE_H)
        screen.blit(font.render(label, True, (200, 200, 200)), (x + SWATCH + 8, y + i * LINE_H))
    for j, note in enumerate(("mixed colour = mixed diet", "brighter cell = in a colony")):
        screen.blit(font.render(note, True, (150, 150, 160)), (x, y + (len(LEGEND) + 1 + j) * LINE_H))


if __name__ == "__main__":
    main()
