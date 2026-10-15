"""
Give the terrain material a fresh, level-specific internal name.

The material was called `cs1_grass` through every iteration while its texture set and texture
paths changed repeatedly.  BeamNG caches compiled terrain materials on disk
(`content/cache/terrainMaterialCache.zip`, and per-user under `temp/art/terrainMaterialCache/`),
keyed by material identity.  Reusing the name across incompatible definitions risks the engine
serving a stale compiled entry -- which would explain why every fix to the material produced the
identical "Missing Terrain texture: /" output regardless of what changed.

A name unique to this level makes each definition a distinct cache key, and matches what working
maps do: `polish_roads_v2` names its material `Asphalt_wet`, `grille_mbwr_city` uses `Dirt`,
neither reusing a name across builds.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# The material internal name is set in __init__.
OLD = '        self.terrain_materials: List[str] = ["cs1_grass"]'
NEW = '''        # Unique per level.  BeamNG caches compiled terrain materials by identity, so reusing a
        # name across different definitions can serve a stale cache entry -- every material fix
        # produced identical "Missing Terrain texture" output, which is consistent with that.
        self.terrain_materials: List[str] = [f"{level_name.lower()}_grass"]'''
if OLD not in src:
    raise SystemExit("terrain_materials anchor not found")
src = src.replace(OLD, NEW, 1)

# Update the stale comment above it if present.
src = src.replace(
    """        # 'grass' is a TerrainMaterial internalName used by multiple shipped levels; an invented
        # name would just fall back to the warning material.
""",
    "",
    1,
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("unique material name :", 'f"{level_name.lower()}_grass"' in src)
print("old name gone        :", '["cs1_grass"]' not in src)
