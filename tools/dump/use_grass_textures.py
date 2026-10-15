"""
Use the engine's tileable GRASS textures, not a satellite map image.

The previous base texture was `t_terrain_base_b.png` from east_coast_usa.  That is a **top-down
satellite image of that level** -- roads, fields and riverbeds visible -- and it is not tileable, so
repeating it drew a visible grid of maps across the ground.  The screenshots show exactly that.

The engine ships proper seamless grass sets in `content/assets/materials/terrain.zip`, each a
complete 1024x1024 family (base colour, normal, roughness, ao, height):

    grass/t_grass_01/       t_grass_01_{b,nm,r,ao,h}.png
    grass/t_grass_02/       t_grass_02_{b,nm,r,ao,h}.png
    grass/ind_grass/        t_ind_grass_{b,nm,r,ao,h}.png
    grass/macro_grass/      t_macro_grass_{b,nm,r,ao,h}.png

Three of them are used, one per scale:

    base    t_grass_02     the ground colour
    macro   t_macro_grass  large-scale variation, breaks up repetition
    detail  ind_grass      fine detail near the camera

All fifteen slots now point at these, so nothing map-like remains.  Tiles are also reduced again:
the request is a small tile, so the base drops from 10 m to 8 m, macro to 2 m and detail to 0.5 m.
"""

import ast
import io
import os
import re

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

BASE = "/assets/materials/terrain/grass/t_grass_02"
MACRO = "/assets/materials/terrain/grass/macro_grass"
DETAIL = "/assets/materials/terrain/grass/ind_grass"

# 15 texture paths: base / macro / detail for each of the five families.
paths = {
    "baseColorBaseTex": f"{BASE}/t_grass_02_b.png",
    "normalBaseTex": f"{BASE}/t_grass_02_nm.png",
    "roughnessBaseTex": f"{BASE}/t_grass_02_r.png",
    "aoBaseTex": f"{BASE}/t_grass_02_ao.png",
    "heightBaseTex": f"{BASE}/t_grass_02_h.png",
    "baseColorMacroTex": f"{MACRO}/t_macro_grass_b.png",
    "normalMacroTex": f"{MACRO}/t_macro_grass_nm.png",
    "roughnessMacroTex": f"{MACRO}/t_macro_grass_r.png",
    "aoMacroTex": f"{MACRO}/t_macro_grass_ao.png",
    "heightMacroTex": f"{MACRO}/t_macro_grass_h.png",
    "baseColorDetailTex": f"{DETAIL}/t_ind_grass_b.png",
    "normalDetailTex": f"{DETAIL}/t_ind_grass_nm.png",
    "roughnessDetailTex": f"{DETAIL}/t_ind_grass_r.png",
    "aoDetailTex": f"{DETAIL}/t_ind_grass_ao.png",
    "heightDetailTex": f"{DETAIL}/t_ind_grass_h.png",
}

block_start = src.index("CS1_TERRAIN_MATERIAL = {")
block_end = src.index("}", block_start) + 1
block = src[block_start:block_end]

replaced = 0
for field, value in paths.items():
    pattern = re.compile(r'("%s":\s*)"[^"]*"' % re.escape(field))
    block, n = pattern.subn(lambda m: m.group(1) + '"' + value + '"', block, count=1)
    replaced += n
if replaced != 15:
    print(f"  warning: replaced {replaced} of 15 texture paths")

# Tiles: smaller again, and the detail family now uses real grass so it can be very fine.
for old, new in (
    ('"baseColorBaseTexSize": 10,', '"baseColorBaseTexSize": 8,'),
    ('"normalBaseTexSize": 10,', '"normalBaseTexSize": 8,'),
    ('"roughnessBaseTexSize": 10,', '"roughnessBaseTexSize": 8,'),
    ('"aoBaseTexSize": 10,', '"aoBaseTexSize": 8,'),
    ('"heightBaseTexSize": 10,', '"heightBaseTexSize": 8,'),
    ('"baseColorMacroTexSize": 4,', '"baseColorMacroTexSize": 2,'),
    ('"normalMacroTexSize": 4,', '"normalMacroTexSize": 2,'),
    ('"roughnessMacroTexSize": 4,', '"roughnessMacroTexSize": 2,'),
    ('"aoMacroTexSize": 4,', '"aoMacroTexSize": 2,'),
    ('"heightMacroTexSize": 4,', '"heightMacroTexSize": 2,'),
    ('"baseColorDetailTexSize": 2,', '"baseColorDetailTexSize": 0.5,'),
    ('"normalDetailTexSize": 2,', '"normalDetailTexSize": 0.5,'),
    ('"roughnessDetailTexSize": 2,', '"roughnessDetailTexSize": 0.5,'),
    ('"aoDetailTexSize": 2,', '"aoDetailTexSize": 0.5,'),
    ('"heightDetailTexSize": 2,', '"heightDetailTexSize": 0.5,'),
    # Grass, not dirt.
    ('"groundmodelName": "DIRT",', '"groundmodelName": "GRASS",'),
    ('"annotation": "DIRT",', '"annotation": "GRASS",'),
    ('"internalName": "Dirt",', '"internalName": "Grass",'),
):
    if old in block:
        block = block.replace(old, new, 1)
    else:
        print("  size/name miss:", old)

src = src[:block_start] + block + src[block_end:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("grass refs:", src.count("/assets/materials/terrain/grass/"))
print("base tile :", '"baseColorBaseTexSize": 8' in src)
print("groundmodel GRASS:", '"groundmodelName": "GRASS"' in src)
