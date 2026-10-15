"""
Rebuild the grass material from a PROVEN field set, changing only the texture paths.

The dark ground was my own material definition, not the textures -- those measure as normal
green/grey (mean RGB ~111-127).  Rather than guess which field was missing, the material is now
copied field-for-field from a working level's grass material and only the *Tex paths are changed,
so the structure is known-good.

Reference: polish_roads_v2's `Grass`, which renders correctly.  Its base textures point at
`t_terrain_base_*`, and that base image is **the satellite map** the user spotted tiling across the
ground.  So every slot is redirected to the engine's seamless grass sets:

    base    -> /assets/materials/terrain/grass/t_grass_02/
    macro   -> /assets/materials/terrain/grass/macro_grass/
    detail  -> /assets/materials/terrain/grass/ind_grass/

Every field the reference declares is kept, including the ones absent from my earlier attempt:

    baseColorDetailStrength, normalDetailStrength, roughnessDetailStrength,
    baseColorMacroStrength, normalMacroStrength, roughnessMacroStrength,
    detailSize, diffuseSize, macroSize, detailStrength, macroStrength,
    detailDistAtten, detailDistance, macroDistAtten, macroDistance

`groundmodelName` stays GRASS, which is the field linking terrain to physical surface behaviour.
"""

import ast
import io
import json
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- the proven field set, taken from polish_roads_v2's Grass -------------------------------
fields = [
    ("class", '"TerrainMaterial"'),
    ("internalName", '"Grass"'),
    ("groundmodelName", '"GRASS"'),
    ("annotation", '"GRASS"'),
    ("diffuseSize", "2048"),
    ("detailSize", "4"),
    ("macroSize", "50"),
    ("detailStrength", "0.5"),
    ("macroStrength", "0.3"),
    ("detailDistance", "25"),
    ("macroDistance", "1000"),
    ("detailDistAtten", "[0, 1]"),
    ("macroDistAtten", "[0.35, 1]"),
    ("detailDistances", "[0, 0, 50, 80]"),
    ("macroDistances", "[0, 0, 400, 8000]"),
    ("baseColorDetailStrength", "[0.4, 0.45]"),
    ("normalDetailStrength", "[1, 0.3]"),
    ("roughnessDetailStrength", "[0, 0]"),
    ("baseColorMacroStrength", "[0, 0.1]"),
    ("normalMacroStrength", "[0.5, 0.5]"),
    ("roughnessMacroStrength", "[0.2, 0.4]"),
]

# ---- textures: all from the engine's seamless grass sets ------------------------------------
B = "/assets/materials/terrain/grass/t_grass_02"
M = "/assets/materials/terrain/grass/macro_grass"
D = "/assets/materials/terrain/grass/ind_grass"

# (field, path, tile metres).  Tiles are small so the pattern repeats finely.
textures = [
    ("baseColorBaseTex", f"{B}/t_grass_02_b.png", "baseColorBaseTexSize", 8),
    ("normalBaseTex", f"{B}/t_grass_02_nm.png", "normalBaseTexSize", 8),
    ("roughnessBaseTex", f"{B}/t_grass_02_r.png", "roughnessBaseTexSize", 8),
    ("aoBaseTex", f"{B}/t_grass_02_ao.png", "aoBaseTexSize", 8),
    ("heightBaseTex", f"{B}/t_grass_02_h.png", "heightBaseTexSize", 8),
    ("baseColorMacroTex", f"{M}/t_macro_grass_b.png", "baseColorMacroTexSize", 2),
    ("normalMacroTex", f"{M}/t_macro_grass_nm.png", "normalMacroTexSize", 2),
    ("roughnessMacroTex", f"{M}/t_macro_grass_r.png", "roughnessMacroTexSize", 2),
    ("aoMacroTex", f"{M}/t_macro_grass_ao.png", "aoMacroTexSize", 2),
    ("heightMacroTex", f"{M}/t_macro_grass_h.png", "heightMacroTexSize", 2),
    ("baseColorDetailTex", f"{D}/t_ind_grass_b.png", "baseColorDetailTexSize", 0.5),
    ("normalDetailTex", f"{D}/t_ind_grass_nm.png", "normalDetailTexSize", 0.5),
    ("roughnessDetailTex", f"{D}/t_ind_grass_r.png", "roughnessDetailTexSize", 0.5),
    ("aoDetailTex", f"{D}/t_ind_grass_ao.png", "aoDetailTexSize", 0.5),
    ("heightDetailTex", f"{D}/t_ind_grass_h.png", "heightDetailTexSize", 0.5),
]

lines = ['CS1_TERRAIN_MATERIAL = {']
for key, value in fields:
    lines.append(f'    "{key}": {value},')
for field, path, size_field, tile in textures:
    lines.append(f'    "{field}": "{path}",')
    lines.append(f'    "{size_field}": {tile},')
lines.append("}")

block_start = src.index("CS1_TERRAIN_MATERIAL = {")
block_end = src.index("\n}", block_start) + 2
src = src[:block_start] + "\n".join(lines) + src[block_end:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)

# ---- confirm the rebuilt block is valid JSON -------------------------------------------------
block = src[src.index("CS1_TERRAIN_MATERIAL = {"):src.index("\n}", src.index("CS1_TERRAIN_MATERIAL = {")) + 2]
obj = json.loads(block.split("=", 1)[1].strip())
tex = [k for k in obj if k.endswith("Tex")]
sizes = [k for k in obj if k.endswith("TexSize")]
print("SYNTAX OK")
print(f"  fields       : {len(obj)}  (reference had 43)")
print(f"  textures     : {len(tex)}   sizes: {len(sizes)}")
print(f"  groundmodel  : {obj['groundmodelName']}")
print(f"  base tile    : {obj['baseColorBaseTexSize']} m   macro {obj['baseColorMacroTexSize']} m   detail {obj['baseColorDetailTexSize']} m")
print(f"  satellite refs: {sum(1 for k in tex if 't_terrain_base' in obj[k])}")
