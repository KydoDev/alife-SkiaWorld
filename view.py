"""Interactive viewer (pygame).

    python view.py [--seed 1] [--scale 6]
    python view.py --load runs/test1/world_final.json.gz
    python view.py --planet examples/volcanic.json      # or an image file

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
from worldsim.render import render_rgb, save_png
from worldsim.worldgen import PlanetError, load_planet
from worldsim.world import GENE_NAMES

PANEL_W = 260
PANEL_TOP = 10
LINE_H = 18
# Tallest panel: 12 stat lines (incl. blank) + 4 cell-header lines (incl. blank) + one line per gene.
PANEL_MAX_LINES = 12 + 4 + len(GENE_NAMES)


def main():
    p = argparse.ArgumentParser(description="WorldSim interactive viewer")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--scale", type=int, default=6)
    p.add_argument("--load", metavar="SAVE", help="open a world_*.json.gz save file instead of a new world")
    p.add_argument("--planet", metavar="FILE", help="generate the world from a planet form (.json) or an image")
    args = p.parse_args()

    if args.load:
        world = load_world(args.load)
        cfg = world.cfg
    elif args.planet:
        try:
            cfg, terrain, seed = load_planet(args.planet)
        except PlanetError as e:
            raise SystemExit(f"Invalid planet: {e}") from e
        world = World(cfg, seed=seed, terrain=terrain)
    else:
        cfg = Config()
        world = World(cfg, seed=args.seed)
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
            f"  plants     {s['photo']}",
            f"  decomp.    {s['sapro']}",
            f"  predators  {s['pred']}",
            f"  chemo      {s['chemo']}",
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

        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
