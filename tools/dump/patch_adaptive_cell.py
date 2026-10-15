"""
Cover the whole map with the terrain, and stop the verifiers demanding `squareSize`.

The working levels have 2 km worlds, so 1 m per cell gives them a 2048 grid.  Cannes spans roughly
8 km, and the heightmap is capped at 8192 cells, so 1 m per cell cannot cover it -- roads and
buildings outside the block then sit on nothing, which is what the verifier reported (mappings off
by kilometres).

The cell size is therefore derived from the extent so the grid stays inside the cap:

    cell = extent / 8192, rounded up to a power of two

That keeps the terrain covering the data, at the finest resolution the grid cap allows.
`squareSize` is written again, because with a cell size other than 1 the engine must be told what
it is; omitting it makes the engine assume 1 m and mis-scale every material.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("def choose_terrain_size(")
end = src.index("\n\n\n", src.index("return resolution, 1.0", start))

NEW = '''def choose_terrain_size(
    extent: float, max_resolution: int = 8192, cell_size: float = 0.0
) -> Tuple[int, float]:
    """
    Choose the heightmap resolution and the metres per grid cell for a map of `extent` metres.

    Both shipped maps that render correctly use 1 m per cell with a 2048 grid, i.e. a 2 km world.
    Cannes spans about 8 km and the heightmap is capped at 8192 cells, so 1 m per cell cannot cover
    it -- roads and buildings outside the block would sit on nothing.

    The cell size is therefore the smallest power of two that lets an 8192-cell grid cover the
    extent, and the grid is the extent divided by it.  `squareSize` is written so the engine scales
    terrain materials to the same world units the grid uses; leaving it out makes the engine assume
    1 m and mis-scale every material.
    """
    if cell_size and cell_size > 0:
        cell = float(cell_size)
    else:
        cell = 1.0
        while extent / cell > max_resolution:
            cell *= 2.0

    resolution = int(extent / cell) + 1
    snapped = 128
    while snapped < resolution and snapped < max_resolution:
        snapped *= 2
    if snapped < resolution:
        snapped = max_resolution

    return snapped, cell'''

src = src[:start] + NEW + src[end:]

# squareSize must be written again: with a cell size other than 1 the engine has to be told.
src = src.replace(
    '            # Working levels carry baseTexSize on the TerrainBlock; the material resolves\n'
    '            # through it.  `squareSize` is deliberately omitted: no shipped level writes it,\n'
    '            # and declaring 16 made the terrain 16x larger than any working map.\n'
    '            "baseTexSize": self.terrain_texture_base_size,',
    '            # The material resolves through this block, and squareSize is what the terrain\n'
    '            # shader uses to convert world position into texture coordinates.  It must be\n'
    '            # written, because the working levels only get away with omitting it by using the\n'
    '            # engine default of 1 m per cell in a 2 km world.\n'
    '            "baseTexSize": self.terrain_texture_base_size,\n'
    '            "squareSize": self.terrain.square_size,',
    1,
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")

# ---- relax the over-strict verifier checks ---------------------------------------------
for path in ("tools/verify_conversion.py", "tools/beamng_convert.py"):
    full = os.path.join(REPO, path)
    text = io.open(full, encoding="utf-8").read()
    changed = False
    for old, new in (
        ("TerrainBlock is missing 'squareSize'", "TerrainBlock is missing 'squareSize'"),
        ('f"{rel}: TerrainBlock missing \'squareSize\'"',
         'f"{rel}: TerrainBlock missing \'squareSize\'"'),
    ):
        pass
    if changed:
        io.open(full, "w", encoding="utf-8", newline="\n").write(text)
    print(f"  {path}: left as is (squareSize is written again, so the check is valid)")
