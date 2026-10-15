"""Reapply the TerrainBlock texture set and the square-heightmap guarantees."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
s = io.open(TARGET, encoding="utf-8").read()


def sub(old, new, label):
    global s
    if old not in s:
        print("  SKIP (not found):", label)
        return False
    s = s.replace(old, new, 1)
    print("  applied:", label)
    return True


# 1. TerrainBlock selects the v1.5 path via our own texture set.
sub(
    """        No materialTextureSet is assigned, so the classic (v1) terrain material path is used and
        no texture arrays have to be authored.""",
    """        materialTextureSet selects the v1.5 PBR terrain material path and must name a
        TerrainMaterialTextureSet that THIS level declares.  Leaving it out drops the level to the
        classic v1 path, where the v1.5 materials cannot be resolved and the ground renders as the
        engine's warning material.""",
    "TerrainBlock docstring",
)

sub(
    '            "squareSize": self.terrain.square_size,',
    '            "materialTextureSet": self.texture_set_name,\n'
    '            "squareSize": self.terrain.square_size,',
    "TerrainBlock materialTextureSet",
)

# 2. Force the working grids square: a rectangular heightmap corrupts the .ter byte layout.
sub(
    "    filled = _fill_gaps(work)",
    "    filled = _as_square(_fill_gaps(work), work_res)",
    "square after gap fill",
)
sub(
    "    normalised_grid = np.clip(smoothed, 0.0, 1.0)",
    "    normalised_grid = _as_square(np.clip(smoothed, 0.0, 1.0), work_res)",
    "square normalised grid",
)
sub(
    "        terrain_grid = _resample(normalised_grid, resolution)",
    "        terrain_grid = _as_square(_resample(normalised_grid, resolution), resolution)",
    "square terrain grid",
)
sub(
    "        png_grid = _resample(normalised_grid, png_resolution)",
    "        png_grid = _as_square(_resample(normalised_grid, png_resolution), png_resolution)",
    "square preview grid",
)

# 3. write_ter_file must refuse a non-square grid.
GUARD = (
    "    # A rectangular heightmap makes the height section the wrong length, which shifts the\n"
    "    # layer map and material list and corrupts the file.  Fail loudly rather than ship that.\n"
    "    if terrain.heights.shape != (terrain.size, terrain.size):\n"
    "        raise ValueError(\n"
    '            f"heightmap must be square ({terrain.size}x{terrain.size}), got '
    '{terrain.heights.shape}"\n'
    "        )\n"
    "    if terrain.layers.shape != (terrain.size, terrain.size):\n"
    "        raise ValueError(\n"
    '            f"layer map must be square ({terrain.size}x{terrain.size}), got '
    '{terrain.layers.shape}"\n'
    "        )\n\n"
)
sub(
    "    height_bytes = np.ascontiguousarray(terrain.heights, dtype=\"<u2\").tobytes()",
    GUARD + "    height_bytes = np.ascontiguousarray(terrain.heights, dtype=\"<u2\").tobytes()",
    "square guard in write_ter_file",
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(s)
print()
print("  TerrainBlock materialTextureSet :", '"materialTextureSet": self.texture_set_name' in s)
print("  _as_square call sites           :", s.count("_as_square("))
print("  square guard present            :", "heightmap must be square" in s)
