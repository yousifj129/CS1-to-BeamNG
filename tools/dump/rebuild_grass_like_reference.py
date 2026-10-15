"""
Rebuild the grass material to the reference structure, with a green base.

WHAT THE IMAGES SHOWED
----------------------
Rendering the three textures the material used made the cause obvious:

    BASE   forest/t_forest_ground_02    green, yellow-green grass and stone flecks
    DETAIL grass/t_grass_02             green/olive, fine
    MACRO  forest/t_macro_forest        RED / brown

The macro layer was RED and tiled at **1 metre**, so it repeated 1024 times and dominated everything
under the camera -- which is why the ground looked red from above and dark mud close up. The green
base was simply buried under it.

(An earlier mean-based scan called this texture "green" because it averages (110, 110, 110)... the
mean of a texture does not describe its appearance. Rendering it did.)

THE REFERENCE STRUCTURE
-----------------------
polish_roads_v2's Grass, field for field:

    baseColorBaseTex             local t_terrain_base_b     size 2048   <- the COLOUR, large and stretched
    baseColorDetailTex           t_grass_01_b               size 3      <- fine detail, subtle
    baseColorMacroTex            t_macro_grass_b            size 80     <- large-scale variation
    baseColorDetailStrength      [0.4, 0.45]
    baseColorMacroStrength       [0, 0.1]
    detailDistances              [0, 0, 50, 80]
    macroDistances               [0, 0, 400, 8000]
    detailSize 4   macroSize 50   detailDistance 25   macroDistance 1000
    detailDistAtten [0,1]   macroDistAtten [0.35,1]

The essential shape of it: the **base** carries the colour and is large (3-2048 m), the **detail** is
tiny (3-5 m) and subtle, and the **macro** is large (50-160 m) and very subtle. Small tiles for the
texture families that only add fine variation; large tiles for anything that would otherwise repeat
visibly.

That is the opposite of what was configured here, where every family was 0.5-4 m.

SO
--
Base becomes the engine's green forest ground at 200 m -- the stand-in for a level's own colour
texture, stretched so no repeat is visible. Detail and macro go back to subtle reference strengths
and reference-scale tiles.

blend strengths are restored to the reference values.
"""

import ast
import io
import os
import re

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("CS1_TERRAIN_MATERIAL = {")
end = src.index("\n}", start)
block = src[start:end]

# --- textures ----------------------------------------------------------------------------------
GREEN = "/assets/materials/terrain/forest/t_forest_ground_02"
G = "/assets/materials/terrain/grass/t_grass_01"
MG = "/assets/materials/terrain/grass/macro_grass"

replacements = {
    "baseColorBaseTex": f"{GREEN}/t_forest_ground_02_b.png",
    "normalBaseTex": f"{GREEN}/t_forest_ground_02_nm.png",
    "roughnessBaseTex": f"{GREEN}/t_forest_ground_02_r.png",
    "aoBaseTex": f"{GREEN}/t_forest_ground_02_ao.png",
    "heightBaseTex": f"{GREEN}/t_forest_ground_02_h.png",
    "baseColorDetailTex": f"{G}/t_grass_01_b.png",
    "normalDetailTex": f"{G}/t_grass_01_nm.png",
    "roughnessDetailTex": f"{G}/t_grass_01_r.png",
    "aoDetailTex": f"{G}/t_grass_01_ao.png",
    "heightDetailTex": f"{G}/t_grass_01_h.png",
    "baseColorMacroTex": f"{MG}/t_macro_grass_b.png",
    "normalMacroTex": f"{MG}/t_macro_grass_nm.png",
    "roughnessMacroTex": f"{MG}/t_macro_grass_r.png",
    "aoMacroTex": f"{MG}/t_macro_grass_ao.png",
    "heightMacroTex": f"{MG}/t_macro_grass_h.png",
}
for field, path in replacements.items():
    block = re.sub(
        r'("%s":\s*)"[^"]*"' % re.escape(field), lambda m: m.group(1) + '"' + path + '"', block, count=1
    )

# --- tiles: the reference's shape, scaled for a much larger world ------------------------------
# The reference's base tile is 2048 m and its macro 80 m.  Ours is 32 km across, so the base is
# stretched further still; the detail sits at the reference's own scale.
sizes = {
    "baseColorBaseTexSize": "200",
    "normalBaseTexSize": "200",
    "roughnessBaseTexSize": "200",
    "aoBaseTexSize": "200",
    "heightBaseTexSize": "200",
    "baseColorDetailTexSize": "4",
    "normalDetailTexSize": "4",
    "roughnessDetailTexSize": "4",
    "aoDetailTexSize": "4",
    "heightDetailTexSize": "4",
    "baseColorMacroTexSize": "60",
    "normalMacroTexSize": "60",
    "roughnessMacroTexSize": "60",
    "aoMacroTexSize": "60",
    "heightMacroTexSize": "60",
}
for field, value in sizes.items():
    block = re.sub(r'("%s":\s*)[\d.]+' % re.escape(field), lambda m: m.group(1) + value, block, count=1)

# --- strengths and distances: the reference's own values ---------------------------------------
ref = {
    "baseColorDetailStrength": "[0.4, 0.45]",
    "baseColorMacroStrength": "[0, 0.1]",
    "normalDetailStrength": "[1, 0.3]",
    "normalMacroStrength": "[0.5, 0.5]",
    "roughnessDetailStrength": "[0, 0]",
    "roughnessMacroStrength": "[0.2, 0.4]",
    "detailDistances": "[0, 0, 50, 80]",
    "macroDistances": "[0, 0, 400, 8000]",
    "detailSize": "4",
    "macroSize": "50",
    "detailDistance": "25",
    "macroDistance": "1000",
    "detailDistAtten": "[0, 1]",
    "macroDistAtten": "[0.35, 1]",
    "detailStrength": "0.5",
    "macroStrength": "0.3",
    "diffuseSize": "2048",
}
for field, value in ref.items():
    if f'"{field}"' in block:
        block = re.sub(
            r'("%s":\s*)(\[[^\]]*\]|[-\d.]+)' % re.escape(field),
            lambda m: m.group(1) + value,
            block,
            count=1,
        )
    else:
        block = block.rstrip().rstrip(",") + f',\n    "{field}": {value},'

src = src[:start] + block + src[end:]
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("green base :", "t_forest_ground_02_b.png" in src)
print("red macro gone:", "t_macro_forest" not in src)
print("base tile 200, detail 4, macro 60")
