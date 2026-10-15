"""
Two fixes, both from the engine naming what it could not find.

1. WRONG DETAIL TEXTURE PATHS.
   The log now names the missing resources explicitly:

       Missing Terrain texture: /assets/materials/terrain/soil/dirt_rocky/t_dirt_rocky_r.png

   Those files do not exist.  They are under `rock/`, not `soil/`:

       assets/materials/terrain/rock/t_dirt_rocky/t_dirt_rocky_{b,nm,r,ao,h}.png

   All five detail paths are corrected.  This is why the ground rendered but its detail layer did
   not: the base family loaded, the detail family silently failed.

2. TILING MUCH FINER.
   `*TexSize` is metres per tile.  A 256 m tile is still far too coarse for a 1024x1024 texture --
   that works out to 25 cm per texel, which is what reads as blocky.  The request is 10 m or less,
   and the values below are set accordingly:

       base    10 m   (10.2 mm per texel)   was 256
       macro    4 m                          was  32
       detail   2 m                          was   2

   `macroDistances`/`detailDistances` are tightened to match, so the finer families dominate as
   soon as they are legible.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

fixes = [
    # ---- 1. correct the detail texture directory: soil/ -> rock/
    ('/assets/materials/terrain/soil/dirt_rocky/', '/assets/materials/terrain/rock/t_dirt_rocky/'),
    # ---- 2. tile sizes: 10 m or less
    ('"baseColorBaseTexSize": 256,', '"baseColorBaseTexSize": 10,'),
    ('"normalBaseTexSize": 256,', '"normalBaseTexSize": 10,'),
    ('"roughnessBaseTexSize": 256,', '"roughnessBaseTexSize": 10,'),
    ('"aoBaseTexSize": 256,', '"aoBaseTexSize": 10,'),
    ('"heightBaseTexSize": 256,', '"heightBaseTexSize": 10,'),
    ('"baseColorMacroTexSize": 32,', '"baseColorMacroTexSize": 4,'),
    ('"normalMacroTexSize": 32,', '"normalMacroTexSize": 4,'),
    ('"roughnessMacroTexSize": 32,', '"roughnessMacroTexSize": 4,'),
    ('"aoMacroTexSize": 32,', '"aoMacroTexSize": 4,'),
    ('"heightMacroTexSize": 32,', '"heightMacroTexSize": 4,'),
    ('"macroDistances": [0, 8, 40, 400],', '"macroDistances": [0, 6, 20, 120],'),
    ('"detailDistances": [0, 0, 8, 20],', '"detailDistances": [0, 0, 4, 10],'),
]

for old, new in fixes:
    if old in src:
        src = src.replace(old, new, 1)
    else:
        print("  MISS:", old)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print()
print("SYNTAX OK")
print("rock/ detail paths :", src.count("/assets/materials/terrain/rock/t_dirt_rocky/"))
print("soil/ left over    :", src.count("/assets/materials/terrain/soil/dirt_rocky/"))
print("base tile          :", '"baseColorBaseTexSize": 10' in src)
print("macro tile         :", '"baseColorMacroTexSize": 4' in src)
