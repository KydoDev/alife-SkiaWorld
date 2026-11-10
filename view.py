"""Visualizzatore interattivo (pygame).

    python view.py [--seed 1] [--scale 6]

Comandi:
  SPAZIO  pausa / riprendi        N  un passo (in pausa)
  + / -   passi per frame         O  mostra/nasconde materia organica
  S       salva snapshot PNG      R  ricomincia (nuovo seed)
  clic    ispeziona una cellula   ESC  esci
"""
import argparse
import random

import numpy as np
import pygame

from worldsim import Config, World
from worldsim.render import render_rgb, save_png
from worldsim.world import GENE_NAMES

PANEL_W = 260


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--scale", type=int, default=6)
    args = p.parse_args()

    cfg = Config()
    world = World(cfg, seed=args.seed)
    sc = args.scale
    pygame.init()
    screen = pygame.display.set_mode((cfg.width * sc + PANEL_W, cfg.height * sc))
    pygame.display.set_caption("WorldSim v0")
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
                    print("Salvato", name)
                elif ev.key == pygame.K_r:
                    world = World(cfg, seed=random.randrange(1_000_000))
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
            f"passo        {s['step']}",
            f"popolazione  {s['population']}",
            f"  piante     {s['photo']}",
            f"  decompos.  {s['sapro']}",
            f"  predatori  {s['pred']}",
            f"in colonia   {s['in_colony']}",
            f"lignaggi     {s['lineages']}",
            f"passi/frame  {steps_per_frame}{'  [PAUSA]' if paused else ''}",
            "",
        ]
        if selected is not None:
            if selected.alive:
                lines += [f"cellula #{selected.id}", f"energia {selected.energy:.1f}  eta {selected.age}",
                          f"legami {len(selected.bonds)}  strategia {selected.strategy}", ""]
                lines += [f"{n:7s} {v:.2f}" for n, v in zip(GENE_NAMES, selected.genes)]
            else:
                lines.append("(cellula morta)")
        else:
            lines.append("clic su una cellula")
        x0 = cfg.width * sc + 12
        for i, t in enumerate(lines):
            screen.blit(font.render(t, True, (220, 220, 220)), (x0, 10 + i * 18))

        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
