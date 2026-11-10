"""World -> RGB image (numpy), used by the viewer and snapshots."""
import numpy as np

# colors per strategy
C_PHOTO = np.array([60, 210, 70], dtype=np.float32)    # green: plants
C_SAPRO = np.array([170, 90, 230], dtype=np.float32)   # purple: decomposers
C_PRED = np.array([235, 50, 45], dtype=np.float32)     # red: predators
C_CHEMO = np.array([40, 215, 225], dtype=np.float32)   # cyan: chemosynthesizers (vents)
C_ROCK = np.array([92, 88, 84], dtype=np.float32)      # grey: rock
C_VENT = np.array([255, 120, 20], dtype=np.float32)    # orange glow: chemical energy
C_ORGANIC = np.array([120, 80, 35], dtype=np.float32)  # brown: organic matter
C_WATER_LIT = np.array([28, 59, 140], dtype=np.float32)  # blue: water at full light (dark = shade/depth)

# (label, colour) pairs for legends; cells mix the first four by their feeding shares
LEGEND = [
    ("plants (photosynthesis)", C_PHOTO), ("decomposers", C_SAPRO), ("predators", C_PRED),
    ("chemosynthesis (vents)", C_CHEMO), ("light (dark = shade)", C_WATER_LIT),
    ("organic matter", C_ORGANIC), ("vent chemical energy", C_VENT), ("rock", C_ROCK),
]


def render_rgb(world, show_organic=True):
    H, W = world.H, world.W
    img = np.zeros((H, W, 3), dtype=np.float32)
    # water: blue proportional to the effective light
    lum = np.clip(world.light / world.cfg.light_max, 0, 1)
    img[..., 0] = 8 + 20 * lum
    img[..., 1] = 14 + 45 * lum
    img[..., 2] = 30 + 110 * lum
    if world.has_chem:
        v = np.clip(world.chem, 0, 1)[..., None] * 0.6
        img = img * (1 - v) + C_VENT * v
    if show_organic:
        o = np.clip(world.organic / 20.0, 0, 1)[..., None]
        img = img * (1 - 0.8 * o) + C_ORGANIC * 0.8 * o
    if world.has_rock:
        img[world.terrain.rock] = C_ROCK

    cells = world.cells
    if cells:
        n = len(cells)
        xs = np.fromiter((c.x for c in cells), np.int32, n)
        ys = np.fromiter((c.y for c in cells), np.int32, n)
        tr = np.array([(c.photo, c.sapro, c.pred, c.chemo) for c in cells], dtype=np.float32)
        col = tr[:, :1] * C_PHOTO + tr[:, 1:2] * C_SAPRO + tr[:, 2:3] * C_PRED + tr[:, 3:4] * C_CHEMO
        # bonded (colony) cells slightly brighter
        bonded = np.fromiter((1.0 if c.bonds else 0.0 for c in cells), np.float32, n)[:, None]
        col = col * (0.85 + 0.15 * bonded) + 25 * bonded
        img[ys, xs] = col
    return np.clip(img, 0, 255).astype(np.uint8)


def save_png(world, path, scale=4):
    from PIL import Image
    img = Image.fromarray(render_rgb(world))
    if scale != 1:
        img = img.resize((world.W * scale, world.H * scale), Image.NEAREST)
    img.save(path)
