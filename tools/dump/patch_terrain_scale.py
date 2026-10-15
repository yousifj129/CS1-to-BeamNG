"""
Match the terrain geometry working levels use.

Measured from two shipped maps that render correctly:

    grille_mbwr_city : squareSize absent, position [-1024, -1024], maxHeight 512
    polish_roads_v2  : squareSize absent, position [-1024, -1024], maxHeight 50

Both are a 2048 x 2048 m span centred on the origin, i.e. 1 m per grid cell, with `squareSize`
never written.  Ours declared `squareSize: 16` and positioned the block at [-16386, -16384], a
32772 m span at 16 m per cell -- sixteen times larger, with one material layer stretched across
all of it.

That difference is the likely cause of `Missing Terrain texture: /`: terrain materials tile in
world units, and the texture arrays are packed per terrain cell.  At 16 m per cell and a single
layer spanning 32 km, the packing has nothing sensible to produce.

The span is now taken from the level's own extent, snapped to a power of two, giving 1 m per cell
exactly as the working maps do, and `squareSize` is omitted.
"""

import io
import ast
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()


def sub(old, new, label):
    global src
    if old not in src:
        print("  SKIP (anchor missing):", label)
        return False
    src = src.replace(old, new, 1)
    print("  applied:", label)
    return True


# ---- 1. omit squareSize, matching every working level ----------------------------------
sub(
    '            # Working levels carry these on the TerrainBlock; the material resolves through it.\n'
    '            "baseTexSize": self.terrain_texture_base_size,\n'
    '            "squareSize": self.terrain.square_size,',
    '            # Working levels carry baseTexSize on the TerrainBlock; the material resolves\n'
    '            # through it.  `squareSize` is deliberately omitted: no shipped level writes it,\n'
    '            # and declaring 16 made the terrain 16x larger than any working map.\n'
    '            "baseTexSize": self.terrain_texture_base_size,',
    "omit squareSize",
)

# ---- 2. force 1 m per cell so the span is 2048 m, as in both working levels -------------
sub(
    "def choose_terrain_size(extent: float, max_resolution: int = 2048) -> Tuple[int, float]:",
    "def choose_terrain_size(\n"
    "    extent: float, max_resolution: int = 2048, cell_size: float = 1.0\n"
    ") -> Tuple[int, float]:",
    "choose_terrain_size takes cell_size",
)

# The body is replaced wholesale so the cell size drives the span rather than the reverse.
start = src.index("def choose_terrain_size(")
end = src.index("\n\n\n", src.index("return resolution, square_size", start))

NEW_BODY = '''def choose_terrain_size(
    extent: float, max_resolution: int = 2048, cell_size: float = 1.0
) -> Tuple[int, float]:
    """
    Pick the heightmap resolution for a map spanning `extent` metres.

    Returns (resolution, square_size) where square_size is the metres per grid cell.

    Both working levels measured use a 2048 m span at 1 m per cell and never write `squareSize`.
    Declaring 16 m per cell made ours 32772 m across -- 16x any shipped map -- with a single
    material layer over the whole thing, which is the setting that produced
    `Missing Terrain texture: /` on every slot.

    The span is the smallest power of two that covers `extent`, capped at 8192 m, and the cell size
    is derived from it so the grid resolution lands at or below `max_resolution`.
    """
    span = 2048.0
    while span < extent and span < 8192.0:
        span *= 2.0

    # 1 m per cell is the working-level default; coarsen only if the grid would exceed the cap.
    cell = cell_size
    resolution = int(span / cell)
    while resolution > max_resolution:
        cell *= 2.0
        resolution = int(span / cell)

    # Heightmaps must be a power of two.
    snapped = 128
    while snapped < resolution:
        snapped *= 2
    return snapped, cell'''

src = src[:start] + NEW_BODY + src[end:]

# ---- 3. centre the block on the origin, as both working levels do ----------------------
sub(
    '            "position": [\n'
    '                round(self.terrain.position_x, 3),\n'
    '                round(self.terrain.position_y, 3),\n'
    '                round(self.terrain.height_min, 3),\n'
    '            ],',
    '            # Both working levels place the block at [-half, -half]; a 2048 m span centred on\n'
    '            # the origin, not a 32 km block offset to a corner.\n'
    '            "position": [\n'
    '                round(-self.terrain.span * 0.5, 3),\n'
    '                round(-self.terrain.span * 0.5, 3),\n'
    '                round(self.terrain.height_min, 3),\n'
    '            ],',
    "centre the terrain block",
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)

try:
    ast.parse(src)
    print("  SYNTAX OK")
except SyntaxError as exc:
    print("  SYNTAX ERROR line", exc.lineno)
    lines = src.split("\n")
    for i in range(max(0, exc.lineno - 4), min(len(lines), exc.lineno + 3)):
        print(f"    {i + 1:>5}| {lines[i][:110]}")
    raise SystemExit(1)

print()
print("  squareSize omitted :", '"squareSize"' not in src or 'squareSize is deliberately omitted' in src)
print("  cell_size 1.0      :", "cell_size: float = 1.0" in src)
