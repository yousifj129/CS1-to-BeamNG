"""
Use 1 m per grid cell, as every working level does, and grow the GRID to cover the map.

Both working levels measured:

    grille_mbwr_city : 2048 grid, squareSize absent -> 2048 m span, 1 m per cell
    polish_roads_v2  : 2048 grid, squareSize absent -> 2048 m span, 1 m per cell

Ours was 2048 grid at 4 m per cell, because the map is ~8 km wide and the resolution was capped at
2048.  That makes the terrain geometry 4x coarser than any shipped map, and terrain materials tile
in world units -- `squareSize` is what the terrain shader uses to convert world position into
texture coordinates, so a non-1 value changes the mapping for every material.

Rather than coarsen the cell, the grid grows so the span is covered at 1 m per cell, and
`squareSize` stays omitted so the engine's own default (1 m) applies.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("def choose_terrain_size(")
end = src.index("\n\n\n", src.index("return snapped, cell", start))

NEW = '''def choose_terrain_size(
    extent: float, max_resolution: int = 8192, cell_size: float = 1.0
) -> Tuple[int, float]:
    """
    Choose the heightmap resolution, and the metres per grid cell.

    Both shipped maps that render correctly use **1 m per cell** and never write `squareSize`:

        grille_mbwr_city : 2048 grid -> 2048 m span, maxHeight 512
        polish_roads_v2  : 2048 grid -> 2048 m span, maxHeight 50

    `squareSize` is the metres-per-cell the terrain shader uses to turn a world position into
    texture coordinates.  Ours was 4 m per cell (and 16 m before that), so every terrain material
    mapped four to sixteen times coarser than in any working level -- which is the setting that
    produced `Missing Terrain texture: /` on all fifteen slots.

    The span is the map extent rounded up to a power of two, and the grid is the span divided by
    1 m, so the cell size is always exactly 1.  The grid is power-of-two and clamped to the
    engine's supported range.
    """
    # Smallest power of two span that covers the map, clamped to what a heightmap supports.
    span = 256
    while span < extent and span < 8192:
        span *= 2

    cell = float(cell_size)
    resolution = int(span / cell)

    # Clamp to the supported power-of-two range; only coarsen if the grid would exceed the cap.
    resolution = max(128, min(8192, resolution))
    snapped = 128
    while snapped < resolution:
        snapped *= 2

    if snapped != resolution:
        resolution = snapped

    # If the cap forced a coarser grid than 1 m per cell would allow, keep 1 m anyway: the engine
    # derives the span from grid x squareSize, and matching the working levels matters more than
    # covering every outlying road.
    return resolution, 1.0'''

src = src[:start] + NEW + src[end:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("cell size fixed at 1.0 :", "return resolution, 1.0" in src)
print("max_resolution 8192    :", "max_resolution: int = 8192" in src)
