"""World seed (F2): build a planet from a photo or from a "create your planet" form.

The input shapes the *environment*; life always starts from random cells. Inputs
are untrusted (they may come from someone else), so both loaders bound their size,
validate every field, and raise `PlanetError` with a readable message. Nothing in
an input is ever executed: JSON is parsed with `json`, images are decoded by Pillow
under a pixel cap.

- Photo: column brightness -> surface sunlight, red -> chemical energy (minerals,
  heat), blue -> initial organic matter (nutrients), strong edges -> rock barriers,
  SHA-256 of the file bytes -> seed (same photo, same world).
- Form (JSON): a handful of planet-level fields mapped onto `Config`; the terrain
  is then generated procedurally from that `Config` and the seed.
"""
import hashlib
import json
import math
from dataclasses import fields
from pathlib import Path

import numpy as np

from .config import MAX_WORLD_TILES, Config
from .terrain import Terrain, generate_terrain

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000          # well below Pillow's own bomb limit
MAX_FORM_BYTES = 64 * 1024
IMAGE_FORMATS = ["PNG", "JPEG", "WEBP", "BMP", "GIF"]   # common, well-trodden decoders only
EDGE_THRESHOLD = 0.25                  # normalized gradient magnitude that becomes rock
ORGANIC_SCALE = 10.0                   # initial organic matter at full blue


class PlanetError(ValueError):
    pass


def seed_from_bytes(data: bytes) -> int:
    """Stable across processes and machines (unlike the salted built-in `hash`)."""
    return int.from_bytes(hashlib.sha256(data).digest()[:4], "big") & 0x7FFFFFFF


# ---------------------------------------------------------------------- photo
def _read_capped(path, limit, what):
    # read at most limit+1 bytes: also safe for pipes/devices whose stat size is meaningless
    path = Path(path)
    try:
        with open(path, "rb") as f:
            data = f.read(limit + 1)
    except OSError as e:
        raise PlanetError(f"cannot read {what} {path}: {e.strerror}") from e
    if len(data) > limit:
        raise PlanetError(f"{what} {path} is larger than the limit ({limit} bytes)")
    return data


def _decode_image(data: bytes, width: int, height: int) -> np.ndarray:
    """Decode and resize to the grid; returns float RGB in [0, 1], shape (H, W, 3)."""
    import io

    from PIL import Image, UnidentifiedImageError
    try:
        im = Image.open(io.BytesIO(data), formats=IMAGE_FORMATS)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as e:
        raise PlanetError(f"not a readable image ({', '.join(IMAGE_FORMATS)}): {e}") from e
    with im:
        # header dimensions are known before any pixel is decoded
        if not 0 < im.width * im.height <= MAX_IMAGE_PIXELS:
            raise PlanetError(f"image is {im.width}x{im.height} (limit {MAX_IMAGE_PIXELS} pixels)")
        try:
            rgb = im.convert("RGB").resize((width, height), Image.BILINEAR)
        except Exception as e:  # decoders raise many types (ValueError, SyntaxError, struct.error...)
            raise PlanetError(f"cannot decode image: {e}") from e
    return np.asarray(rgb, dtype=np.float64) / 255.0


def terrain_from_rgb(rgb: np.ndarray, cfg: Config) -> Terrain:
    H, W, _ = rgb.shape
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    terrain = Terrain.flat(W, H)

    # bright columns get more sun; mean-normalized so a photo changes where light falls,
    # not how much energy the planet receives in total
    sun = 0.25 + lum.mean(axis=0)
    terrain.sun = sun / sun.mean()

    # strong edges -> rock barriers (geographic isolation); the surface row stays water
    gy, gx = np.gradient(lum)
    # sqrt of the sum of squares, not np.hypot: IEEE-exact on every platform and in Rust (G2_PLAN);
    # equal to np.hypot on Windows' libm, while CPython's math.hypot is not libm and differs
    grad = np.sqrt(gx * gx + gy * gy)
    if grad.max() > 0:
        grad /= grad.max()
    terrain.rock = grad >= EDGE_THRESHOLD
    terrain.rock[0] = False

    redness = np.clip(r - 0.5 * (g + b), 0.0, 1.0)
    terrain.chem = cfg.vent_strength * redness
    terrain.organic = ORGANIC_SCALE * b
    terrain.chem[terrain.rock] = 0.0
    terrain.organic[terrain.rock] = 0.0
    return terrain


def planet_from_image(path, cfg: Config) -> tuple[Terrain, int]:
    """Terrain shaped by the image at `path`, and the seed derived from its bytes."""
    _check_size(cfg)
    data = _read_capped(path, MAX_IMAGE_BYTES, "image")
    return terrain_from_rgb(_decode_image(data, cfg.width, cfg.height), cfg), seed_from_bytes(data)


# ----------------------------------------------------------------------- form
# star type -> (surface light, day length in steps)
STARS = {"red_dwarf": (0.6, 400), "sun": (1.0, 200), "blue_giant": (1.6, 100)}

# form field -> (type, min, max)
FORM_FIELDS = {
    "name": (str, None, None),
    "seed": (int, 0, 2**31 - 1),
    "star": (str, None, None),
    "seasonality": (float, 0.0, 0.9),        # season_amplitude
    "day_night": (float, 0.0, 1.0),          # day_amplitude
    "ocean_depth": (float, 5.0, 200.0),      # light_depth (rows)
    "seabed_relief": (float, 0.0, 0.6),      # rock_fraction
    "volcanism": (int, 0, 50),               # vent_count
    "mineral_richness": (float, 0.0, 10.0),  # vent_strength
    "config": (dict, None, None),            # raw Config overrides, validated field by field
}


def _check_value(key, value, kind, lo, hi):
    if kind is float and isinstance(value, int) and not isinstance(value, bool):
        try:
            value = float(value)
        except OverflowError as e:
            raise PlanetError(f"form field {key!r} is too large") from e
    if not isinstance(value, kind) or (isinstance(value, bool) and kind is not bool):
        raise PlanetError(f"form field {key!r} must be {kind.__name__}, got {type(value).__name__}")
    if kind is float and not math.isfinite(value):
        raise PlanetError(f"form field {key!r} must be finite")
    if lo is not None and not lo <= value <= hi:
        raise PlanetError(f"form field {key!r} = {value} is outside [{lo}, {hi}]")
    return value


def _check_size(cfg: Config):
    if not (2 <= cfg.width and 2 <= cfg.height and cfg.width * cfg.height <= MAX_WORLD_TILES):
        raise PlanetError(f"world size {cfg.width}x{cfg.height} is outside the supported range")


def _validate(cfg: Config) -> Config:
    try:
        return cfg.validate()
    except ValueError as e:
        raise PlanetError(str(e)) from e


def config_from_form(form: dict, base: Config | None = None) -> tuple[Config, int | None]:
    if not isinstance(form, dict):
        raise PlanetError("a planet form must be a JSON object")
    unknown = set(form) - set(FORM_FIELDS)
    if unknown:
        raise PlanetError(f"unknown form fields: {', '.join(sorted(unknown))}")
    cfg = base or Config()
    v = {k: _check_value(k, form[k], *FORM_FIELDS[k]) for k in form}

    if "star" in v:
        if v["star"] not in STARS:
            raise PlanetError(f"unknown star {v['star']!r}; choose one of {', '.join(STARS)}")
        cfg.light_max, cfg.day_length = STARS[v["star"]]
    for key, attr in (("seasonality", "season_amplitude"), ("day_night", "day_amplitude"),
                      ("ocean_depth", "light_depth"), ("seabed_relief", "rock_fraction"),
                      ("volcanism", "vent_count"), ("mineral_richness", "vent_strength")):
        if key in v:
            setattr(cfg, attr, v[key])

    types = {f.name: type(f.default) for f in fields(Config)}
    for k, val in v.get("config", {}).items():
        if k not in types:
            raise PlanetError(f"unknown Config field {k!r} in form 'config'")
        setattr(cfg, k, _check_value(f"config.{k}", val, types[k], None, None))
    _check_size(cfg)
    return _validate(cfg), v.get("seed")


def planet_from_form(path, base: Config | None = None, seed: int | None = None) -> tuple[Config, Terrain, int]:
    """Config, procedural terrain and seed from a JSON planet form. An explicit `seed`
    overrides the form's own (or the one derived from its content)."""
    data = _read_capped(path, MAX_FORM_BYTES, "planet form")
    try:
        form = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:     # ValueError: JSONDecodeError and huge ints
        raise PlanetError(f"planet form {path} is not valid JSON: {e}") from e
    cfg, form_seed = config_from_form(form, base)
    if seed is None:
        seed = form_seed
    if seed is None:
        seed = seed_from_bytes(json.dumps(form, sort_keys=True).encode("utf-8"))
    return cfg, generate_terrain(cfg, seed), seed


def load_planet(path, base: Config | None = None, seed: int | None = None) -> tuple[Config, Terrain, int]:
    """Dispatch on the extension: `.json` is a form, anything else an image.
    An explicit `seed` replaces the planet's own seed for the dynamics (and for a form's terrain)."""
    if str(path).lower().endswith(".json"):
        return planet_from_form(path, base, seed)
    cfg = _validate(base or Config())
    terrain, image_seed = planet_from_image(path, cfg)
    return cfg, terrain, image_seed if seed is None else seed
