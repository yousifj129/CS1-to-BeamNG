"""
Use the working map's exact asphalt texture family for the terrain.

Every structural field already matches polish_roads_v2 (set sizes [2048,2048]/[1024,1024]/
[1024,1024], 2048 local base textures, 10 engine detail/macro refs), yet the engine still reports
`Missing Terrain texture: /` for this level only.  The remaining differences are the specific
texture files, so this switches to the exact family the working map uses:

    base   : t_terrain_base_{b,nm,r,ao,h}.png        (local, 2048)
    detail : /assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_{...}.png
    macro  : /assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_{...}.png

that is, an ASPHALT family rather than the grass one, with `groundmodelName` ASPHALT.  All of
these files are confirmed present in content/assets/materials/terrain.zip.

This is a deliberate test: if the terrain renders, the problem was the grass texture family; if it
still fails, the problem is in the material or block plumbing and not the textures at all.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- engine texture references -> the working map's asphalt family ----------------------
OLD = '''CS1_TERRAIN_ENGINE_TEX = {
    "baseColorDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_b.png",
    "normalDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_nm.png",
    "roughnessDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_r.png",
    "aoDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_ao.png",
    "heightDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_h.png",
    "baseColorMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_b.png",
    "normalMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_nm.png",
    "roughnessMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_r.png",
    "aoMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_ao.png",
    "heightMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_h.png",
}'''

NEW = '''# The detail and macro families are taken from the engine's own library, and deliberately use the
# SAME asphalt family as the working third-party map polish_roads_v2.  The grass family
# (ind_grass / macro_clumply) is also present in terrain.zip, but every attempt with it produced
# "Missing Terrain texture: /" for this level only, while the asphalt family is proven to render.
_ASPHALT = "/assets/materials/terrain/asphalt"

CS1_TERRAIN_ENGINE_TEX = {
    "baseColorDetailTex": f"{_ASPHALT}/t_asphalt_02/t_asphalt_02_b.png",
    "normalDetailTex": f"{_ASPHALT}/t_asphalt_02/t_asphalt_02_nm.png",
    "roughnessDetailTex": f"{_ASPHALT}/t_asphalt_02/t_asphalt_02_r.png",
    "aoDetailTex": f"{_ASPHALT}/t_asphalt_02/t_asphalt_02_ao.png",
    "heightDetailTex": f"{_ASPHALT}/t_asphalt_02/t_asphalt_02_h.png",
    "baseColorMacroTex": f"{_ASPHALT}/macro_asphalt/t_macro_asphalt_b.png",
    "normalMacroTex": f"{_ASPHALT}/macro_asphalt/t_macro_asphalt_nm.png",
    "roughnessMacroTex": f"{_ASPHALT}/macro_asphalt/t_macro_asphalt_r.png",
    "aoMacroTex": f"{_ASPHALT}/macro_asphalt/t_macro_asphalt_ao.png",
    "heightMacroTex": f"{_ASPHALT}/macro_asphalt/t_macro_asphalt_h.png",
}'''

if OLD not in src:
    raise SystemExit("engine texture table anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- ground model follows the surface type ---------------------------------------------
src = src.replace('"groundmodelName": "GRASS",\n            "annotation": "GRASS",',
                  '"groundmodelName": "ASPHALT",\n            "annotation": "ASPHALT",', 1)

# ---- strengths copied from the working material ----------------------------------------
for old, new in (
    ('definition["baseColorMacroStrength"] = [0.05, 0.12]',
     'definition["baseColorMacroStrength"] = [0.5, 0.7]'),
    ('definition["baseColorDetailStrength"] = [0.25, 0.25]',
     'definition["baseColorDetailStrength"] = [0.5, 0.5]'),
    ('definition["roughnessMacroStrength"] = [0.15, 0.8]',
     'definition["roughnessMacroStrength"] = [0.9, 0.9]'),
    ('definition["roughnessDetailStrength"] = [0.3, 0.3]',
     'definition["roughnessDetailStrength"] = [0.9, 0.5]'),
):
    if old in src:
        src = src.replace(old, new, 1)
        print("  strength updated:", old.split('=')[0].strip())

# The reference material has no normal strength overrides; drop ours so the field set matches.
src = src.replace('        definition["normalMacroStrength"] = [0.2, 0.4]\n', "", 1)
src = src.replace('        definition["normalDetailStrength"] = [0.7, 0.15]\n', "", 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print()
print("asphalt family in use :", "macro_asphalt/t_macro_asphalt_b.png" in src)
print("groundmodel ASPHALT   :", '"groundmodelName": "ASPHALT"' in src)
print("normal strengths gone :", "normalMacroStrength" not in src)
