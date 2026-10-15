"""
Define the asphalt terrain material and paint the roads into the layer map.

The asphalt material is derived from the grass one so that every field a working material declares
is present, with only these changed:

    internalName / annotation   -> Asphalt
    groundmodelName             -> ASPHALT   (the physics link)
    all fifteen textures        -> the engine's built-in asphalt terrain sets

Engine asphalt sets live under `assets/materials/terrain/asphalt/`; the details used here are
verified to resolve.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

ASPHALT_BLOCK = '''

# ==========================================================================================
#  Asphalt terrain material -- the road surface
# ==========================================================================================
#
# Derived from the grass material so every field a working material declares is present.  Only the
# identity, the physics link and the fifteen texture paths differ.
#
# `groundmodelName: "ASPHALT"` is the important one: it is what makes the painted road surface grip
# like a road.  The level's `groundModels/surfaces.json` overrides that model with firm coefficients.
#
# Textures are the engine's built-in asphalt terrain sets.
ASPHALT_BASE = "/assets/materials/terrain/asphalt/t_asphalt_02"
ASPHALT_MACRO = "/assets/materials/terrain/asphalt/macro_asphalt"
ASPHALT_DETAIL = "/assets/materials/terrain/asphalt/t_asphalt_02"

CS1_ASPHALT_MATERIAL = dict(CS1_TERRAIN_MATERIAL)
CS1_ASPHALT_MATERIAL.update({
    "internalName": "Asphalt",
    "annotation": "ASPHALT",
    "groundmodelName": "ASPHALT",
    "baseColorBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_b.png",
    "normalBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_nm.png",
    "roughnessBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_r.png",
    "aoBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_ao.png",
    "heightBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_h.png",
    "baseColorMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_b.png",
    "normalMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_nm.png",
    "roughnessMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_r.png",
    "aoMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_ao.png",
    "heightMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_h.png",
    "baseColorDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_b.png",
    "normalDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_nm.png",
    "roughnessDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_r.png",
    "aoDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_ao.png",
    "heightDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_h.png",
})
'''

# Place it immediately after the grass material definition (after its closing brace).
anchor = "\nCS1_TERRAIN_TEXTURE_SET = {"
if anchor not in src:
    raise SystemExit("texture set anchor not found")
src = src.replace(anchor, ASPHALT_BLOCK + anchor, 1)

# ---- paint the roads after the terrain exists ------------------------------------------------
OLD = """        self.terrain = build_terrain(
            self.layout,
            self.roads,
            heightmap_size=self.heightmap_size,
            verbose=False,
        )"""
NEW = """        self.terrain = build_terrain(
            self.layout,
            self.roads,
            heightmap_size=self.heightmap_size,
            verbose=False,
        )

        # Paint the road footprint into the terrain's material layer map.  This is what gives roads
        # their own surface: a DecalRoad is only a decal and carries no grip, so without this the
        # whole map drives as one surface and roads feel like the ground they are drawn on.
        painted = apply_road_surface(self.terrain, self.roads)
        self.report["roadSurfaceCells"] = painted"""
if OLD not in src:
    raise SystemExit("build_terrain call anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("asphalt material :", "CS1_ASPHALT_MATERIAL" in src)
print("roads painted    :", "apply_road_surface(self.terrain" in src)
