"""
Declare baseTexSize 1024 -- the size the engine textures actually are.

The log was explicit:

    E|TerrainCellMaterial| Terrain material [Grass] using texture
    [/assets/materials/terrain/grass/t_grass_02/t_grass_02_b.png]
    dont have required size of 2048-2048 declared in TerrainMaterialTextureSet
    named [CannesTerrainMaterialTextureSet]

`baseTexSize` is a REQUIRED pixel size, not a hint.  Every texture in a family must match it, or the
engine discards it and packs a black layer -- which is exactly the permanent black ground.

The value 2048 was inherited from the material's origin: it started as a copy of east_coast_usa's
terrain material, whose base family (`t_terrain_base_*`) genuinely is 2048x2048.  But every grass
and asphalt set used here comes from `content/assets/materials/terrain.zip`, and measuring all 213
PNGs in that archive shows they are **all 1024x1024** -- 38 complete sets, not one larger.

So the declared size must be 1024.  The `*TexSize` tiling fields are a different thing entirely
(world metres per tile) and are left alone.

The check that would have caught this immediately: compare each texture's real pixel size against
the declared size.  That is now in the conformance report.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = '''CS1_TERRAIN_TEXTURE_SET = {
    "class": "TerrainMaterialTextureSet",
    "baseTexSize": [2048, 2048],
    "detailTexSize": [1024, 1024],
    "macroTexSize": [1024, 1024],
}'''

NEW = '''# `baseTexSize` is a REQUIRED pixel size: every texture in a family must match it or the engine
# discards the texture and packs a black layer.  All 213 PNGs in `content/assets/materials/
# terrain.zip` are 1024x1024 (38 complete sets, none larger), so 1024 is the only correct value for
# materials drawing from that archive.  The previous 2048 came from east_coast_usa, whose own
# `t_terrain_base_*` family is genuinely 2048 -- copying its material copied its required size too,
# and every grass texture was then rejected as the wrong size.
CS1_TERRAIN_TEXTURE_SET = {
    "class": "TerrainMaterialTextureSet",
    "baseTexSize": [1024, 1024],
    "detailTexSize": [1024, 1024],
    "macroTexSize": [1024, 1024],
}'''

if OLD not in src:
    raise SystemExit("texture set anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("baseTexSize now 1024:", '"baseTexSize": [1024, 1024]' in src)
