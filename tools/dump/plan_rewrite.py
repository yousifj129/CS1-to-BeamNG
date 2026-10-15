"""
Rebuild the emission layer of tools/beamng_convert.py from scratch.

Strategy
--------
The core module (value types, layout parsing, transforms, terrain reconstruction, .ter writing,
PNG encoding) is 41 functions and 1386 lines of code that has been verified and is not implicated
in any of the failures.  It is preserved verbatim.

Everything above it -- the level builder and its emit_* methods, plus thirteen rounds of
accumulated patches (duplicated terrain constants, a dead `copy_terrain_textures`, a
`provision_skeleton_terrain`, two `emit_terrain_materials`, ...) is deleted and rewritten against
the findings in docs/POLISH_ROADS_REFERENCE.md.

What the new emission layer does differently, in every case because a working map was measured:

  * ONE terrain material, taken verbatim from an ENGINE level and rewritten only so its texture
    paths point at that same engine level.  No material is authored.
  * ZERO textures copied.  All fifteen slots reference engine content in place -- ten from
    /assets/materials/terrain/... and five from the source level's art/terrains/ directory.  This
    is the mechanism polish_roads_v2 uses when it references east_coast_usa textures, and it is
    proven to resolve.
  * TerrainBlock carries the fields a working map carries, including lightMapSize, and its
    baseTexSize equals the texture set's base size.
  * .ter version 9 with all FIVE sections, length asserted.
  * Roads: one DecalRoad per chained centre-line, parented to the folder that owns it, with
    autoJunction and autoLanes ENABLED by explicit instruction.  Decal parameters taken from the
    measured value distributions.
  * Buildings: base-game shapes referenced IN PLACE (never copied, which produced "No Mesh"), each
    grounded on the highest surface under its footprint.
  * Groups: line-delimited, a SimGroup per folder, __parent naming the owning group.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")

src = io.open(TARGET, encoding="utf-8").read()
lines = src.split("\n")

# ---------------------------------------------------------------------------------------------
# 1. Determine the exact line ranges to keep.
# ---------------------------------------------------------------------------------------------
KEEP_MARKERS = [
    ("def to_beamng(", "def to_beamng("),
]

# The core section runs from the first dataclass-era helper to the end of `locate_layout`, and the
# replacement region runs from the first builder-related definition to just before the core
# helpers that follow it.  Rather than guess, locate the two anchors explicitly.

# Anchor A: the terrain material constants block begins the emission layer.
# Anchor B: the first core helper that must survive (`to_beamng`).
a = next(i for i, l in enumerate(lines) if l.startswith("def to_beamng("))
print(f"core helpers begin at line {a + 1}: {lines[a][:60]}")

# The classes Vec3/Bezier/Road/Building/CityLayout/Terrain sit just above the core helpers and are
# kept as-is; only the emission layer below them is replaced.
b = next(i for i, l in enumerate(lines) if l.startswith("class Vec3"))
print(f"value types begin at line {b + 1}")

# The emission layer starts at the first terrain-material constant, which is above the builders.
emission_start = next(
    i for i, l in enumerate(lines)
    if l.startswith("def build_material_definitions(")
)
print(f"emission layer begins at line {emission_start + 1}")

# Everything from emission_start to the end is replaced, except the core helpers that live after
# it.  Report which functions exist after emission_start so nothing is silently lost.
import ast
tree = ast.parse(src)
after = [
    (n.name, n.lineno, n.end_lineno)
    for n in tree.body
    if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.lineno > emission_start
]
print(f"\ndefinitions after the emission start ({len(after)}):")
for name, s, e in after:
    print(f"   {name:<34} lines {s}-{e}")
