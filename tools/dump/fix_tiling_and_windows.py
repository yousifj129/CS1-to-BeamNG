"""
1. Tile the terrain texture much more finely.
2. Give the buildings a built-in window material.

TILING
------
The `*TexSize` fields are the world size one texture tile covers, in metres.  Ours came from
east_coast_usa, which is a large open-world map where one 2048 m tile is reasonable -- but our
terrain spans 32.7 km, so a single tile smears across a huge area and reads as pixelated blocks.

`macroDistances` and `detailDistances` are the split distances at which the macro and detail
families take over.  Ours were `[0, 10, 100, 3000]` and `[0, 0, 30, 60]`, which keeps the enormous
base texture visible out to 3000 m.  Both are tightened so the finer families dominate close in.

BUILDING WINDOWS
----------------
Several base-game building shapes declare materials whose textures live in their own level's
archive, so they resolve only as a placeholder when the shape is referenced from another level --
that is the pale "no material" window strip in the screenshots.

The engine DOES ship window materials as global content, in `content/art_shapes.zip`:

    /art/shapes/objects/m_windows_glass_01/main.materials.json          lit windows, emissive
    /art/shapes/objects/m_transparent_glass_window/main.materials.json  clear coated glass
    /art/shapes/objects/windows_doors_reflective/main.materials.json    reflective glazing

Those are mounted globally, so a level can use them by name.  A `main.materials.json` is written
beside the building assets that re-declares the material names the base-game shapes use, aliasing
each one to the engine's own glass material via `mapTo`.  Nothing new is authored: the entries are
one-line redirects to built-in materials.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- 1. tighter terrain tiling ----------------------------------------------------------
# Base: 2048 m per tile -> 256 m.  Macro: 80 -> 32.  Detail: 4 -> 2.
replacements = [
    ('"baseColorBaseTexSize": 2048,', '"baseColorBaseTexSize": 256,'),
    ('"normalBaseTexSize": 2048,', '"normalBaseTexSize": 256,'),
    ('"roughnessBaseTexSize": 2048,', '"roughnessBaseTexSize": 256,'),
    ('"aoBaseTexSize": 2048,', '"aoBaseTexSize": 256,'),
    ('"heightBaseTexSize": 2048,', '"heightBaseTexSize": 256,'),
    ('"baseColorMacroTexSize": 80,', '"baseColorMacroTexSize": 32,'),
    ('"normalMacroTexSize": 80,', '"normalMacroTexSize": 32,'),
    ('"roughnessMacroTexSize": 80,', '"roughnessMacroTexSize": 32,'),
    ('"aoMacroTexSize": 80,', '"aoMacroTexSize": 32,'),
    ('"heightMacroTexSize": 80,', '"heightMacroTexSize": 32,'),
    ('"baseColorDetailTexSize": 4,', '"baseColorDetailTexSize": 2,'),
    ('"normalDetailTexSize": 4,', '"normalDetailTexSize": 2,'),
    ('"roughnessDetailTexSize": 4,', '"roughnessDetailTexSize": 2,'),
    ('"aoDetailTexSize": 4,', '"aoDetailTexSize": 2,'),
    ('"heightDetailTexSize": 4,', '"heightDetailTexSize": 2,'),
    # Bring the finer families in much sooner so the base tile is only visible at a distance.
    ('"macroDistances": [0, 10, 100, 3000],', '"macroDistances": [0, 8, 40, 400],'),
    ('"detailDistances": [0, 0, 30, 60],', '"detailDistances": [0, 0, 8, 20],'),
]
for old, new in replacements:
    if old in src:
        src = src.replace(old, new, 1)
    else:
        print("  miss:", old)

# ---- 2. engine window material aliases --------------------------------------------------
WINDOW_BLOCK = '''

# ==========================================================================================
#  Window materials for the base-game building shapes
# ==========================================================================================
#
# Several shipped building shapes declare materials whose textures live in their own level's
# archive.  Referenced from another level those textures do not resolve, and the windows render as
# a pale untextured strip -- visible as "no material" boxes in game.
#
# The engine ships window materials as global content inside `content/art_shapes.zip`, mounted for
# every level:
#
#     /art/shapes/objects/m_windows_glass_01/          lit windows, emissive at night
#     /art/shapes/objects/m_transparent_glass_window/  clear-coated glass
#     /art/shapes/objects/windows_doors_reflective/    reflective glazing
#
# The entries below create NO new material.  Each is a one-line redirect: the name a building shape
# asks for, aliased via `mapTo` to the engine's own glass material.  Anything not listed keeps the
# shape's original assignment.
# ==========================================================================================
BUILDING_WINDOW_MATERIAL = "m_windows_glass_01"

# Material names used by the base-game building shapes that should read as glazing.
BUILDING_WINDOW_ALIASES = [
    "windows_glass",
    "windows_glass_01",
    "windows_glass_02",
    "window_glass",
    "glass",
    "glass_window",
    "windows",
    "windows_doors",
    "windows_doors_reflective",
    "m_windows_glass_01",
    "m_transparent_glass_window",
    "building_windows",
    "t_windows_glass_01",
]


def build_window_material_aliases() -> Dict[str, Any]:
    """
    Aliases that redirect a building shape's window material to an engine glass material.

    Each entry is `{name, mapTo}` only -- no stages, no parameters -- so the engine resolves the
    target material itself.  This authors nothing; it points a locally-unknown name at a built-in
    one.
    """
    return {
        alias: {
            "name": alias,
            "mapTo": BUILDING_WINDOW_MATERIAL,
            "class": "Material",
        }
        for alias in BUILDING_WINDOW_ALIASES
    }
'''

anchor = "# ==========================================================================================\n#  Level builder"
if anchor not in src:
    raise SystemExit("level builder banner not found")
src = src.replace(anchor, WINDOW_BLOCK.strip() + "\n\n\n" + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)

import ast

ast.parse(src)
print()
print("SYNTAX OK")
print("base tile 256 :", '"baseColorBaseTexSize": 256' in src)
print("macro tile 32 :", '"baseColorMacroTexSize": 32' in src)
print("detail tile 2 :", '"baseColorDetailTexSize": 2' in src)
print("aliases added :", "def build_window_material_aliases(" in src)
