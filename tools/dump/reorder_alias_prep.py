"""Prepare the window aliases before the material file is written."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = """        self.select_content()
        self.build_terrain()
        self.emit_terrain_materials()"""
NEW = """        self.select_content()
        self.build_terrain()
        # Prepare the window alias table BEFORE the terrain material file is written: the aliases
        # are merged into that file, and `emit_terrain_materials` would otherwise run first and
        # write a file without them.  That ordering mistake is why the aliases had no effect.
        self.emit_building_materials()
        self.emit_terrain_materials()"""
if OLD not in src:
    raise SystemExit("build order anchor not found")
src = src.replace(OLD, NEW, 1)

# The later call is now redundant.
OLD_LATER = """        self.emit_roads()
        # Material aliases must exist before the building shapes that reference them are loaded.
        self.emit_building_materials()
        self.emit_buildings()"""
NEW_LATER = """        self.emit_roads()
        self.emit_buildings()"""
if OLD_LATER in src:
    src = src.replace(OLD_LATER, NEW_LATER, 1)
    print("removed the now-redundant second call")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("call count:", src.count("self.emit_building_materials()"))
