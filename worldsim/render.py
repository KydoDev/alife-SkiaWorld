"""Conversione del mondo in immagine RGB (numpy), usata da viewer e snapshot."""
import numpy as np

# colori per strategia
C_PHOTO = np.array([60, 210, 70], dtype=np.float32)    # verde: piante
C_SAPRO = np.array([170, 90, 230], dtype=np.float32)   # viola: decompositori
C_PRED = np.array([235, 50, 45], dtype=np.float32)     # rosso: predatori


def render_rgb(world, show_organic=True):
    H, W = world.H, world.W
    img = np.zeros((H, W, 3), dtype=np.float32)
    # acqua: blu proporzionale alla luce effettiva
    lum = np.clip(world.light / world.cfg.light_max, 0, 1)
    img[..., 0] = 8 + 20 * lum
    img[..., 1] = 14 + 45 * lum
    img[..., 2] = 30 + 110 * lum
    if show_organic:
        o = np.clip(world.organic / 20.0, 0, 1)[..., None]
        img = img * (1 - 0.8 * o) + np.array([120, 80, 35], dtype=np.float32) * 0.8 * o

    cells = world.cells
    if cells:
        n = len(cells)
        xs = np.fromiter((c.x for c in cells), np.int32, n)
        ys = np.fromiter((c.y for c in cells), np.int32, n)
        tr = np.array([(c.photo, c.sapro, c.pred) for c in cells], dtype=np.float32)
        col = tr[:, :1] * C_PHOTO + tr[:, 1:2] * C_SAPRO + tr[:, 2:3] * C_PRED
        # cellule in colonia leggermente più chiare
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
