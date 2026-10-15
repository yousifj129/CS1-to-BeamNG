"""
Emit the terrain material BEFORE the TerrainBlock.

`emit_terrain_materials()` is what determines `terrain_texture_base_size`, which the TerrainBlock
writes as `baseTexSize`.  The build ran it last, so the block was emitted while the field still
held its initial value of 1024 -- producing a TerrainBlock whose `baseTexSize` disagreed with the
texture set's `[4096,4096]`.  Both working levels have these equal, and the material is resolved
through the block.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = """        self.emit_roads()
        self.emit_buildings()
        self.emit_terrain_block()
        self.emit_sky_and_sun()
        self.emit_spawns_and_mission()
        self.emit_terrain_materials()
        self.emit_terrain_files()"""

NEW = """        self.emit_roads()
        self.emit_buildings()
        # The terrain material must be emitted BEFORE the TerrainBlock, because it determines
        # `terrain_texture_base_size` and the block writes that as `baseTexSize`.  Running it
        # afterwards left the block declaring 1024 while the texture set declared 4096.
        self.emit_terrain_materials()
        self.emit_terrain_block()
        self.emit_sky_and_sun()
        self.emit_spawns_and_mission()
        self.emit_terrain_files()"""

if OLD not in src:
    raise SystemExit("build order anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("materials before block:", src.index("self.emit_terrain_materials()") < src.index("self.emit_terrain_block()"))
