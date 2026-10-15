"""
Put the window aliases where the engine already loads materials from.

The earlier attempt wrote them to `levels/Cannes/main.materials.json` and
`art/shapes/<mod>/main.materials.json`.  Neither is a path this engine reads for a level: it reads
`levels/<level>/art/terrains/main.materials.json`, which is exactly where the terrain material
already loads successfully from -- proven by the ground rendering.

So the aliases now go into that same file, as additional top-level keys alongside the terrain
material and its texture set.  If the engine loads the file for the terrain, it registers the
aliases too, with no new lookup path involved.

This still authors nothing: each alias is `{name, mapTo}` only, redirecting the name a base-game
building shape asks for to a glass material that `content/art_shapes.zip` provides globally.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = '''        aliases = build_window_material_aliases()

        # Materials shipped alongside a mod's shapes are resolved from the mod's art/ tree.
        shape_dir = os.path.join(self.mod_root, "art", "shapes", self.mod_name)
        os.makedirs(shape_dir, exist_ok=True)
        self.write_json(os.path.join(shape_dir, "main.materials.json"), aliases)

        # Also beside the level itself, which is the other place the engine looks for a level's
        # material library.
        self.write_json(
            os.path.join(self.level_root, "main.materials.json"), aliases
        )

        self.report["windowMaterialAliases"] = len(aliases)'''

NEW = '''        # Store them on the builder so the terrain material emitter can merge them into the ONE
        # file the engine demonstrably reads for this level:
        # `levels/<level>/art/terrains/main.materials.json`.  The aliases are merged there rather
        # than written to a separate path, because a file the engine does not read resolves
        # nothing -- which is why the previous attempt had no effect.
        self.window_material_aliases = build_window_material_aliases()
        self.report["windowMaterialAliases"] = len(self.window_material_aliases)'''

if OLD not in src:
    raise SystemExit("building-materials emitter anchor not found")
src = src.replace(OLD, NEW, 1)

# Merge the aliases into the terrain material file.
OLD_WRITE = '''        definitions = {
            f"{self.level_name}TerrainMaterialTextureSet": texture_set,
            f"{material_name}-{new_id()}": definition,
        }

        terrain_dir = os.path.join(self.level_root, "art", "terrains")'''
NEW_WRITE = '''        definitions = {
            f"{self.level_name}TerrainMaterialTextureSet": texture_set,
            f"{material_name}-{new_id()}": definition,
        }

        # Merge the building window aliases into this same file.  It is the one material library
        # the engine is known to load for this level -- the terrain material resolves from here --
        # so a shape's window material is redirected without relying on any other lookup path.
        definitions.update(getattr(self, "window_material_aliases", {}))

        terrain_dir = os.path.join(self.level_root, "art", "terrains")'''
if OLD_WRITE not in src:
    raise SystemExit("terrain write anchor not found")
src = src.replace(OLD_WRITE, NEW_WRITE, 1)

# `emit_building_materials` no longer writes files, so it no longer needs to run before buildings;
# it just prepares the alias table.  Keep the call where it is for clarity.
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("aliases merged into the terrain material file:", "definitions.update(getattr(self" in src)
print("no separate alias files written        :", "shape_dir, \"main.materials.json\"" not in src)
