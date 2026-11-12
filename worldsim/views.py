"""Read-only views of a world for front-ends: the reference of the kernel's ABI 4 views (ADR-0016).

`tile_words` packs what stands on each tile into one 32-bit word, `cell_record` is the inspector's record of one cell.
Pure functions of the saved state: no RNG draw, nothing written, so the state hash is untouched. The Rust kernel
(`engine-rs/src/views.rs`) must give the same bytes; `scripts/g3_view_vectors.py` writes the golden vectors.
"""
import math
import struct

from .world import N_GENES, TRAITS

KIND_EMPTY, KIND_PHOTO, KIND_SAPRO, KIND_PRED, KIND_CHEMO = range(5)
KEY_MOD = 1 << 16          # species key = lineage mod 65536 (lineage until the species tracker is ported, P8)
_WORD = struct.Struct("<I")


def kind(cell) -> int:
    """1 + the index of `Cell.strategy` among (photo, sapro, pred, chemo); the first wins a tie."""
    shares = (cell.photo, cell.sapro, cell.pred, cell.chemo)
    return 1 + shares.index(max(shares))


def _ieee_div(a: float, b: float) -> float:
    """a / b as IEEE-754 (and Rust) divides: a zero divisor gives a signed infinity or NaN, never an exception.
    `div_thr` can be exactly 0 (`div_min` may be 0 and a gene can mutate to 0)."""
    if b != 0.0:
        return a / b
    if a != a or a == 0.0:
        return math.nan
    return math.copysign(math.inf, a) * math.copysign(1.0, b)


def energy_level(cell) -> int:
    """floor(16 * energy / div_thr) clamped to 0..15 (15: about to divide); NaN gives 0."""
    return energy_level_of(float(cell.energy), float(cell.div_thr))


def energy_level_of(energy: float, div_thr: float) -> int:
    q = 16.0 * _ieee_div(energy, div_thr)
    if not q >= 0.0:
        return 0
    return 15 if q >= 15.0 else math.floor(q)


def chem_level(chem: float) -> int:
    """The vent field as `render_rgb` clips it, in four levels: min(3, floor(clip01(chem) * 4)); NaN gives 0."""
    if not chem > 0.0:
        return 0
    return 3 if chem >= 0.75 else math.floor(chem * 4.0)


def tile_word(world, x: int, y: int) -> int:
    """The 32-bit word of tile (x, y) (layout in ADR-0016 Decision 1)."""
    t = world.terrain
    word = (int(bool(t.rock[y, x])) << 4) | (chem_level(float(t.chem[y, x])) << 5)
    c = world.grid[y * world.W + x]
    if c is not None:
        word |= kind(c) | (int(bool(c.bonds)) << 3)
        word |= energy_level(c) << 8
        word |= (c.lineage % KEY_MOD) << 16
    return word


def tile_words(world) -> bytes:
    """Every tile's word, row-major from the lit surface, little-endian: an RGBA32 image."""
    out = bytearray(world.W * world.H * 4)
    for y in range(world.H):
        for x in range(world.W):
            _WORD.pack_into(out, (y * world.W + x) * 4, tile_word(world, x, y))
    return bytes(out)


def colony_size(cell) -> int:
    """Cells in the bonded component of `cell`, itself included (1 when unbonded)."""
    seen, stack = {cell.id}, [cell]
    while stack:
        for b in stack.pop().bonds:
            if b.id not in seen:
                seen.add(b.id)
                stack.append(b)
    return len(seen)


def cell_record(world, x: int, y: int) -> dict:
    """The inspector record of the cell on (x, y) (ADR-0016 Decision 2); `present` 0 and zeros on an empty tile.
    Raises ValueError for a tile outside the world, as the kernel refuses it."""
    if not (0 <= x < world.W and 0 <= y < world.H):
        raise ValueError(f"tile ({x}, {y}) outside the {world.W}x{world.H} world")
    c = world.grid[y * world.W + x]
    if c is None:
        return {"present": 0, "id": 0, "lineage": 0, "age": 0, "energy": 0.0, "genes": [0.0] * N_GENES,
                "shares": [0.0] * 4, "traits": [0.0] * len(TRAITS), "bonds": 0, "colony": 0, "rules": 0}
    return {"present": 1, "id": c.id, "lineage": c.lineage, "age": c.age, "energy": float(c.energy),
            "genes": [float(g) for g in c.genes], "shares": [float(c.photo), float(c.sapro), float(c.pred),
                                                              float(c.chemo)],
            "traits": [float(getattr(c, t.name)) for t in TRAITS], "bonds": len(c.bonds),
            "colony": colony_size(c), "rules": len(c.rules)}

