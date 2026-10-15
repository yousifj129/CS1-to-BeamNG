"""Ensure uuid is imported, then verify the terrain method is the copied one."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

if "import uuid" not in src:
    src = src.replace("import struct\n", "import struct\nimport uuid\n", 1)
    print("added: import uuid")
else:
    print("uuid already imported")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")

# Which terrain method is in place?
has_copy = "copy_grille_terrain" in src
has_engine_table = "CS1_TERRAIN_ENGINE_TEX" in src
print("uses copied working material :", has_copy)
print("still has the invented table :", has_engine_table)
print("TerrainBlock baseTexSize     :", '"baseTexSize": self.terrain_texture_base_size' in src)
print("screenError 64               :", '"screenError": 64' in src)
