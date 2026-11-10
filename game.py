"""Planet in a jar — G1 playable prototype (pygame).

    python game.py                                   # "Volcanic ocean" (examples/volcanic.json)
    python game.py --planet examples/volcanic.json   # or a photo: --planet photo.jpg
    python game.py --set rock_fraction=0.2 --seed 7

You shape the planet, life does the rest. Spend divine energy (it regenerates)
on interventions and try to reach the five milestones. See docs/USER_MANUAL.md.

Controls:
  1-5          choose a tool (nutrients, meteorite, mountain, dig, volcano)
  left click   use the tool (hold and drag for mountain / dig)
  right click  inspect a cell
  SPACE pause · + / - speed · O organic overlay · R new life on the original planet · ESC quit
"""
import argparse
import random

import numpy as np
import pygame

from view import SWATCH, add_world_args, create_world, draw_swatch
from worldsim.play import MILESTONES, TOOLS, Game
from worldsim.render import LEGEND, render_rgb

PANEL_W = 340
LINE_H = 18
PAD = 10
TOOL_KEYS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4}
TOOL_HELP = {
    "nutrients": "drop organic food",
    "meteorite": "wipe out an area",
    "mountain": "raise rock (drag)",
    "dig": "remove rock (drag)",
    "volcano": "open a vent",
}
DRAG_TOOLS = ("mountain", "dig")
TOAST_FRAMES = 300
TEXT, DIM, GOLD, OFF = (220, 220, 220), (140, 140, 150), (240, 200, 80), (90, 90, 100)
DEFAULT_PLANET = "examples/volcanic.json"
INTRO = "Shape the planet; life does the rest. Reach the 5 milestones on the right."


def wrap(text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if font.size(trial)[0] <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


class GameApp:
    def __init__(self, game, scale):
        self.game, self.sc = game, scale
        cfg = game.world.cfg
        self.world_w, self.world_h = cfg.width * scale, cfg.height * scale
        pygame.init()
        self.font = pygame.font.SysFont("consolas", 15)
        self.big = pygame.font.SysFont("consolas", 18, bold=True)
        height = max(self.world_h + 60, 660)
        self.screen = pygame.display.set_mode((self.world_w + PANEL_W, height))
        pygame.display.set_caption("WorldSim — planet in a jar")
        self.clock = pygame.time.Clock()
        self.tool = 0
        self.paused, self.speed, self.show_org = False, 2, True
        self.selected = None
        self.toasts = [[INTRO, TOAST_FRAMES]]
        self.last_drag = None

    # ------------------------------------------------------------ input
    def world_pos(self, pos):
        x, y = pos[0] // self.sc, pos[1] // self.sc
        w = self.game.world
        return (x, y) if 0 <= x < w.W and 0 <= y < w.H else None

    def use_tool(self, pos):
        tile = self.world_pos(pos)
        if tile is None:
            return
        tool = TOOLS[self.tool]
        if not self.game.act(tool, *tile) and not self.game.can_afford(tool):
            self.toast(f"Not enough divine energy for {tool}")

    def toast(self, text):
        if not self.toasts or self.toasts[-1][0] != text:
            self.toasts.append([text, TOAST_FRAMES])

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            return False
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                return False
            if ev.key in TOOL_KEYS:
                self.tool = TOOL_KEYS[ev.key]
            elif ev.key == pygame.K_SPACE:
                self.paused = not self.paused
            elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.speed = min(self.speed * 2, 32)
            elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.speed = max(self.speed // 2, 1)
            elif ev.key == pygame.K_o:
                self.show_org = not self.show_org
            elif ev.key == pygame.K_r:
                self.game.restart(random.randrange(1_000_000))
                self.selected = None
                self.toast("New life on the original planet (milestones kept)")
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:
                self.use_tool(ev.pos)
                self.last_drag = self.world_pos(ev.pos)
            elif ev.button == 3:
                tile = self.world_pos(ev.pos)
                self.selected = self.game.world.cell_at(*tile) if tile else None
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.last_drag = None
        elif (ev.type == pygame.MOUSEMOTION and ev.buttons[0] and TOOLS[self.tool] in DRAG_TOOLS
              and self.last_drag is not None):
            tile = self.world_pos(ev.pos)
            if tile is not None and tile != self.last_drag:
                self.use_tool(ev.pos)
                self.last_drag = tile
        return True

    # ------------------------------------------------------------ drawing
    def text(self, s, x, y, color=TEXT, font=None):
        self.screen.blit((font or self.font).render(s, True, color), (x, y))

    def draw_world(self):
        w = self.game.world
        img = render_rgb(w, show_organic=self.show_org)
        surf = pygame.surfarray.make_surface(np.transpose(img, (1, 0, 2)))
        self.screen.blit(pygame.transform.scale(surf, (self.world_w, self.world_h)), (0, 0))
        mouse = pygame.mouse.get_pos()
        if self.world_pos(mouse) is not None:
            r = self.game.rules.radius[TOOLS[self.tool]]
            pygame.draw.circle(self.screen, (255, 255, 255), mouse, max(r, 1) * self.sc, 1)
        if self.selected is not None and self.selected.alive:
            s = self.selected
            pygame.draw.rect(self.screen, (255, 255, 255), (s.x * self.sc - 2, s.y * self.sc - 2,
                                                            self.sc + 4, self.sc + 4), 1)

    def draw_bottom_bar(self):
        y = self.world_h + 8
        w = self.game.world
        s = w.stats()
        status = (f"step {s['step']}   population {s['population']}   species {s.get('species', '-')}   "
                  f"light {s['light_factor']:.2f}   speed x{self.speed}{'   [PAUSED]' if self.paused else ''}")
        self.text(status, PAD, y)
        if self.selected is not None and self.selected.alive:
            c = self.selected
            self.text(f"cell #{c.id}: {c.strategy}, energy {c.energy:.0f}, age {c.age}, colony bonds "
                      f"{len(c.bonds)}", PAD, y + LINE_H, DIM)
        else:
            self.text("right click a cell to inspect it", PAD, y + LINE_H, DIM)

    def draw_panel(self):
        g, x0 = self.game, self.world_w + PAD
        width = PANEL_W - 2 * PAD
        y = PAD
        self.text("Divine energy", x0, y, font=self.big)
        y += 24
        frac = g.budget / g.rules.budget_max
        pygame.draw.rect(self.screen, (60, 60, 70), (x0, y, width, 12))
        pygame.draw.rect(self.screen, GOLD, (x0, y, int(width * frac), 12))
        self.text(f"{g.budget:.0f}", x0 + width - 30, y - 18, DIM)
        y += 24
        for i, tool in enumerate(TOOLS):
            cost = g.rules.cost[tool]
            color = TEXT if g.can_afford(tool) else OFF
            if i == self.tool:
                pygame.draw.rect(self.screen, (55, 55, 75), (x0 - 4, y - 1, width + 8, LINE_H))
            self.text(f"{i + 1} {tool:9s} {cost:3.0f}  {TOOL_HELP[tool]}", x0, y, color)
            y += LINE_H
        y += 14
        self.text(f"Milestones {len(g.achieved)}/{len(MILESTONES)}", x0, y, font=self.big)
        y += 26
        for key, desc in MILESTONES.items():
            done = key in g.achieved
            mark = "[x]" if done else "[ ]"
            lines = wrap(f"{mark} {desc}" + (f" (step {g.achieved[key]})" if done else ""), self.font,
                         width - self.font.size("    ")[0])
            for j, line in enumerate(lines):
                self.text(line if j == 0 else "    " + line, x0, y, GOLD if done else TEXT)
                y += LINE_H
            y += 4
        y += 10
        for label, color in LEGEND:
            draw_swatch(self.screen, color, x0, y)
            self.text(label, x0 + SWATCH + 8, y, DIM)
            y += LINE_H - 2

    def draw_toasts(self):
        for msg in self.game.news:
            self.toast(f"Milestone! {msg}")
        if self.game.news and len(self.game.achieved) == len(MILESTONES):
            self.toast(f"All milestones reached at step {self.game.world.step_count}. The jar is yours.")
        self.game.news.clear()
        for t in self.toasts:
            t[1] -= 1
        self.toasts = [t for t in self.toasts if t[1] > 0][-3:]
        top = 10
        for t in self.toasts:
            lines = wrap(t[0], self.big, self.world_w - 40)
            h = len(lines) * 22 + 12
            box = pygame.Surface((self.world_w - 20, h), pygame.SRCALPHA)
            box.fill((10, 10, 20, 200))
            self.screen.blit(box, (10, top))
            for j, line in enumerate(lines):
                self.text(line, 20, top + 6 + j * 22, GOLD, self.big)
            top += h + 6

    def run(self):
        running = True
        while running:
            for ev in pygame.event.get():
                running = self.handle(ev) and running
            if not self.paused:
                for _ in range(self.speed):
                    self.game.step()
            self.screen.fill((18, 18, 24))
            self.draw_world()
            self.draw_bottom_bar()
            self.draw_panel()
            self.draw_toasts()
            pygame.display.flip()
            self.clock.tick(30)
        pygame.quit()


def main():
    p = argparse.ArgumentParser(description="WorldSim — planet in a jar (G1 prototype)")
    add_world_args(p)
    args = p.parse_args()
    if not (args.planet or args.load or args.set):
        args.planet = DEFAULT_PLANET     # all five milestones verified reachable here (scripted playtest)
    GameApp(Game(create_world(args)), args.scale).run()


if __name__ == "__main__":
    main()
