"""Write the window-material alias file and call it from the build."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

METHOD = '''    def emit_building_materials(self) -> None:
        """
        Write window-material aliases beside the level's building assets.

        Several base-game building shapes declare materials whose textures live in their own
        level's archive; referenced from another level those textures do not resolve and the
        windows render as a pale untextured strip.

        Each entry below authors nothing -- it is `{name, mapTo}` only, redirecting the name the
        shape asks for to an engine glass material that IS mounted globally.  Anything not listed
        keeps its original assignment.
        """
        aliases = build_window_material_aliases()

        # Materials shipped alongside a mod's shapes are resolved from the mod's art/ tree.
        shape_dir = os.path.join(self.mod_root, "art", "shapes", self.mod_name)
        os.makedirs(shape_dir, exist_ok=True)
        self.write_json(os.path.join(shape_dir, "main.materials.json"), aliases)

        # Also beside the level itself, which is the other place the engine looks for a level's
        # material library.
        self.write_json(
            os.path.join(self.level_root, "main.materials.json"), aliases
        )

        self.report["windowMaterialAliases"] = len(aliases)

'''

anchor = "    # ---------------------------------------------------------------- lighting"
if anchor not in src:
    raise SystemExit("lighting section anchor not found")
src = src.replace(anchor, METHOD + anchor, 1)

# Call it just before the buildings are emitted, so the aliases exist when the shapes load.
OLD_CALL = """        self.emit_roads()
        self.emit_buildings()
        self.emit_sky_and_sun()"""
NEW_CALL = """        self.emit_roads()
        # Material aliases must exist before the building shapes that reference them are loaded.
        self.emit_building_materials()
        self.emit_buildings()
        self.emit_sky_and_sun()"""
if OLD_CALL not in src:
    raise SystemExit("build call anchor not found")
src = src.replace(OLD_CALL, NEW_CALL, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("method defined:", "def emit_building_materials(" in src)
print("method called :", "self.emit_building_materials()" in src)
