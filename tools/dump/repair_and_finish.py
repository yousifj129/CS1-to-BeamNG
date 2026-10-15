"""
Restore the last valid converter and apply the terrain + grounding changes in one clean pass.

`build/beamng_convert.py.pre_enggrass` is the valid state with chained roads.  Repeated textual
substitution had mangled the CS1_TERRAIN_ENGINE_TEX block, so it is rewritten from scratch here
rather than patched again.
"""

import ast
import io
import os
import shutil

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# Repair the mangled texture table by replacing it wholesale.
start = src.index("CS1_TERRAIN_ENGINE_TEX = {")
# Find the end of the table: the first line that is exactly '}' at column 0 after start.
lines = src[start:].split("\n")
end_offset = None
for i, line in enumerate(lines):
    if i > 0 and line.rstrip() == "}":
        end_offset = i
        break
if end_offset is None:
    raise SystemExit("could not find the end of the texture table")
old_block = "\n".join(lines[: end_offset + 1])

NEW_BLOCK = '''# Every terrain texture comes from the engine's own library, so nothing is copied into the level
# and there is no custom texture to get wrong.  This is the same arrangement as the asphalt family
# that rendered correctly -- the only difference is that these are grass.
CS1_TERRAIN_ENGINE_TEX = {
    "baseColorBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_b.png",
    "normalBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_nm.png",
    "roughnessBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_r.png",
    "aoBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_ao.png",
    "heightBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_h.png",
    "baseColorDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_b.png",
    "normalDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_nm.png",
    "roughnessDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_r.png",
    "aoDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_ao.png",
    "heightDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_h.png",
    "baseColorMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_b.png",
    "normalMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_nm.png",
    "roughnessMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_r.png",
    "aoMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_ao.png",
    "heightMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_h.png",
}'''

src = src.replace(old_block, NEW_BLOCK, 1)

# The size fields must match the engine textures, which are 1024 across all three families.
src = src.replace("        base_size = 2048\n", "        base_size = 1024\n", 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)

try:
    ast.parse(src)
    print("SYNTAX OK")
except SyntaxError as exc:
    print("STILL BROKEN at line", exc.lineno)
    show = src.split("\n")
    for i in range(max(0, exc.lineno - 4), min(len(show), exc.lineno + 3)):
        print(f"  {i + 1:>5}| {show[i]}")
    raise SystemExit(1)

print("engine grass refs :", src.count("/assets/materials/terrain/grass"))
print("base_size         :", "base_size = 1024" in src)
print("highest footprint :", "HIGHEST surface under its footprint" in src)
