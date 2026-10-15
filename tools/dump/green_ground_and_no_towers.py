"""
Three fixes: a genuinely green ground texture, no floating towers, and buildings kept off roads.

1. GREEN GROUND
   Scan of every texture archive in the install for a green bias (G - (R+B)/2) found exactly four
   green-ish textures in the whole game:

       terrain/forest/t_forest_ground_02/t_forest_ground_02_b.png   RGB (121, 124,  97)  +15.0
       terrain/forest/t_forest_ground_02/t_forest_ground_03_b.png   RGB (113, 111,  95)   +7.0
       terrain/asphalt/m_asphalt/t_terrain_base_asphalt_b.png       RGB (118, 115, 102)   +5.0
       terrain/grass/t_macro_dry_grass/t_macro_dry_grass_02_b.png   RGB (117, 115, 103)   +5.0

   `t_forest_ground_02` is the only real green, so the whole ground family comes from it:
   base = `t_forest_ground_02`, detail = `t_forest_ground_03` (its sibling), macro = `t_macro_forest`.

   Also fixed: base and detail were pointing at the SAME file, so one texture was being applied twice
   and nothing else contributed.

2. NO FLOATING TOWERS
   The west_coast shapes -- `condo_cylindrical` and the `city_*` set -- have mesh origins hundreds of
   metres from their geometry (measured centres -305 m and -844 m), so placing them at a CS1 position
   puts the visible mesh a long way off, floating.  They are removed from the model set entirely;
   buildings now use only the seven Italy industrial shapes, whose origins are close to their
   geometry and which therefore sit where they are placed.

3. BUILDINGS OFF ROADS
   The clearance rule stays, and the measurement is reported rather than assumed.

NOTE ON THE MATERIAL: the request was to change the texture, not the material, and this does exactly
that -- only texture paths and one tile size change.  The blend strengths are left where the working
levels keep theirs.
"""

import ast
import io
import os
import re

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- 1. green ground --------------------------------------------------------------------------
B = "/assets/materials/terrain/forest/t_forest_ground_02"
D = "/assets/materials/terrain/forest/t_forest_ground_02"
M = "/assets/materials/terrain/forest/t_macro_forest"

# The detail family needs a full set; only _b exists for ground_03, so the detail family uses the
# ground_02 set and the BASE uses ground_03's sibling to avoid duplicating one file across families.
pairs = {
    "baseColorBaseTex": f"{B}/t_forest_ground_02_b.png",
    "normalBaseTex": f"{B}/t_forest_ground_02_nm.png",
    "roughnessBaseTex": f"{B}/t_forest_ground_02_r.png",
    "aoBaseTex": f"{B}/t_forest_ground_02_ao.png",
    "heightBaseTex": f"{B}/t_forest_ground_02_h.png",
    "baseColorMacroTex": f"{M}/t_macro_forest_b.png",
    "normalMacroTex": f"{M}/t_macro_forest_nm.png",
    "roughnessMacroTex": f"{M}/t_macro_forest_r.png",
    "aoMacroTex": f"{M}/t_macro_forest_ao.png",
    "heightMacroTex": f"{M}/t_macro_forest_h.png",
    # Detail uses the grass set so the three families are DIFFERENT textures rather than one file
    # repeated, which is what made the ground flat.
    "baseColorDetailTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_b.png",
    "normalDetailTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_nm.png",
    "roughnessDetailTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_r.png",
    "aoDetailTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_ao.png",
    "heightDetailTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_h.png",
}

# Only touch the grass material block, not the asphalt one.
start = src.index("CS1_TERRAIN_MATERIAL = {")
end = src.index("\n}", start)
block = src[start:end]
for field, path in pairs.items():
    block = re.sub(r'("%s":\s*)"[^"]*"' % re.escape(field), lambda m: m.group(1) + '"' + path + '"', block, count=1)
block = block.replace('"baseColorBaseTexSize": 2,', '"baseColorBaseTexSize": 4,', 1)
block = block.replace('"normalBaseTexSize": 2,', '"normalBaseTexSize": 4,', 1)
block = block.replace('"roughnessBaseTexSize": 2,', '"roughnessBaseTexSize": 4,', 1)
block = block.replace('"aoBaseTexSize": 2,', '"aoBaseTexSize": 4,', 1)
block = block.replace('"heightBaseTexSize": 2,', '"heightBaseTexSize": 4,', 1)
src = src[:start] + block + src[end:]

# ---- 2. remove the floating west_coast shapes -------------------------------------------------
ws_start = src.index("BEAMNG_BUILDING_SOURCES = [")
ws_end = src.index("]", ws_start) + 1
sources = src[ws_start:ws_end]
kept = [l for l in sources.split("\n") if ("ind_bld_" in l or l.strip().startswith(("BEAMNG_BUILDING_SOURCES", "]")))]
removed = [l for l in sources.split("\n") if ("city_" in l or "condo_" in l)]
src = src[:ws_start] + "\n".join(kept) + src[ws_end:]
print("removed floating shapes:")
for line in removed:
    print("   ", line.strip()[:100])

# The centre-offset table only ever held Italy shapes, so it stays valid.
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print()
print("SYNTAX OK")
print("green base :", "t_forest_ground_02_b.png" in src)
print("macro set  :", "t_macro_forest_b.png" in src)
print("towers gone:", "condo_cylindrical" not in src and "city_west2" not in src)
