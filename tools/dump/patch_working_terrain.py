"""
Replace the terrain material with a verbatim copy of a working third-party level's setup.

The engine reports `Missing Terrain texture: /` for every slot of the template-derived material,
even though the textures exist in the level and their pixel sizes match the declared
TerrainMaterialTextureSet exactly (base 512, macro/detail 1024).  Rather than keep guessing which
path form the engine accepts, this copies the material AND its textures out of a level that is
known to render -- grille_mbwr_city, a shipped third-party map -- and rewrites only the texture
paths so they point at the copies inside our level.

Its textures are already in the loose PNG form the engine resolves, unlike the template's set
which mixes .png, .dds and `.link` placeholder files.
"""

import io
import json
import os
import re
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
SOURCE_ZIP = os.path.join(
    os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo",
    "grille_mbwr_city.zip",
)
SOURCE_LEVEL = "grille_mbwr_city"


def read_source():
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        material_member = None
        for entry in archive.infolist():
            if re.search(r"art/terrains?/main\.materials\.json$", entry.filename, re.I):
                material_member = entry.filename
                break
        if material_member is None:
            raise SystemExit("no terrain material file in the source level")

        data = json.loads(archive.read(material_member).decode("utf-8", "replace"))

        material = None
        texture_set = None
        for value in data.values():
            if not isinstance(value, dict):
                continue
            if value.get("class") == "TerrainMaterial" and material is None:
                material = value
            elif value.get("class") == "TerrainMaterialTextureSet":
                texture_set = value

        # Collect every texture the material references, and pull the bytes for those that live
        # inside the source level.
        textures = {}
        for field, value in material.items():
            if not (isinstance(value, str) and field.endswith("Tex")):
                continue
            normalised = value.replace("\\", "/")
            base = os.path.basename(normalised)
            member = f"levels/{SOURCE_LEVEL}/art/terrains/{base}"
            try:
                textures[base] = archive.read(member)
            except KeyError:
                textures[base] = None

    return material, texture_set, textures


material, texture_set, textures = read_source()
print("source material :", material.get("internalName"))
print("texture set     :", (texture_set or {}).get("name"))
print("textures:")
for name, blob in sorted(textures.items()):
    print(f"   {name:<44} {'%d bytes' % len(blob) if blob else 'NOT IN SOURCE LEVEL'}")

missing = [n for n, b in textures.items() if b is None]

# ---- emit the patch ---------------------------------------------------------------------
BLOCK = '''# ==========================================================================================
#  Terrain material, taken verbatim from a working third-party level.
#
#  The template-derived material was rejected by the engine with
#      E|TerrainCellMaterial| Missing Terrain texture: /
#  for all 15 slots, even though the textures were present in the level and their pixel sizes
#  matched the declared TerrainMaterialTextureSet exactly.  The template set mixes .png, .dds
#  and `.link` placeholder files, which is the likely reason the paths do not resolve.
#
#  grille_mbwr_city is a shipped third-party map that renders, and its textures are plain PNGs
#  beside the level.  Its material and textures are copied here, with only the texture paths
#  rewritten to point at the copies inside this level.
# ==========================================================================================
CS1_TERRAIN_MATERIAL = ''' + repr(material) + '''

CS1_TERRAIN_TEXTURE_SET = ''' + repr(texture_set) + '''

# base filename -> source path inside grille_mbwr_city
CS1_TERRAIN_TEXTURE_SOURCES = {
''' + "".join(
    f"    {name!r}: 'levels/{SOURCE_LEVEL}/art/terrains/{name}',\n"
    for name, blob in sorted(textures.items()) if blob is not None
) + '''}


def copy_working_terrain_textures(destination_dir: str) -> Dict[str, str]:
    """
    Copy a working level's terrain textures into this level.

    Textures must live inside the level -- a level cannot resolve another level's or the game's
    asset textures by path -- so the bytes are copied rather than referenced.
    """
    import zipfile

    game = find_beamng_install()
    os.makedirs(destination_dir, exist_ok=True)
    copied: Dict[str, str] = {}
    if not game:
        return copied

    archive_path = os.path.join(game, "content", "levels", "grille_mbwr_city.zip")
    if not os.path.isfile(archive_path):
        # Fall back to the installed copy under the user's mods folder.
        archive_path = os.path.join(
            os.path.expandvars(r"%LOCALAPPDATA%"), "BeamNG", "BeamNG.drive", "current",
            "mods", "repo", "grille_mbwr_city.zip",
        )
    if not os.path.isfile(archive_path):
        return copied

    with zipfile.ZipFile(archive_path) as archive:
        for name, member in CS1_TERRAIN_TEXTURE_SOURCES.items():
            try:
                blob = archive.read(member)
            except KeyError:
                continue
            target = os.path.join(destination_dir, name)
            with open(target, "wb") as handle:
                handle.write(blob)
            copied[name] = target
    return copied


'''

anchor = "def emit_terrain_materials(self) -> None:"
src = io.open(TARGET, encoding="utf-8").read()
if anchor not in src:
    raise SystemExit("anchor not found")
class_at = src.index("class BeamNGLevelBuilder")
src = src[:class_at] + BLOCK + src[class_at:]

# ---- replace the body of emit_terrain_materials ----------------------------------------
start = src.index(anchor)
end = src.index("\n    def emit_preview_image", start)

NEW_METHOD = '''    def emit_terrain_materials(self) -> None:
        """
        Emit a TerrainMaterial and its TerrainMaterialTextureSet, copied from a level that renders.

        The material is CS1_TERRAIN_MATERIAL (grille_mbwr_city's), with every texture path rewritten
        to a copy inside this level.  The texture set is likewise copied so the declared pixel
        sizes match the textures that ship with it -- the engine packs them into arrays and a
        mismatch drops the whole material to WARNING_MATERIAL.
        """
        if self.terrain is None:
            return

        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)

        copied = copy_working_terrain_textures(terrain_dir)
        for _name, path in sorted(copied.items()):
            self.report["files"].append(os.path.relpath(path, self.mod_root))
        if not copied:
            self.report["warnings"].append(
                "no terrain textures could be copied; the ground will render untextured"
            )

        vfs = f"/levels/{self.level_name.lower()}/art/terrains"

        definition: Dict[str, Any] = {}
        for field, value in CS1_TERRAIN_MATERIAL.items():
            if isinstance(value, str) and field.endswith("Tex"):
                definition[field] = f"{vfs}/{os.path.basename(value.replace(chr(92), '/'))}"
            else:
                definition[field] = value
        definition["internalName"] = self.terrain_materials[0]
        definition["persistentId"] = new_id()

        texture_set = dict(CS1_TERRAIN_TEXTURE_SET or {})
        texture_set["name"] = self.texture_set_name
        texture_set["persistentId"] = new_id()

        definitions = {
            f"{self.level_name}TerrainMaterialTextureSet": texture_set,
            f"{self.terrain_materials[0]}-{new_id()}": definition,
        }

        # art/terrains/ is the modern location; art/terrain/ is still read by some paths, so the
        # textures are mirrored beside it too.
        legacy = os.path.join(self.level_root, "art", "terrain")
        os.makedirs(legacy, exist_ok=True)
        for name, path in copied.items():
            with open(path, "rb") as source, open(os.path.join(legacy, name), "wb") as target:
                target.write(source.read())
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)
        self.write_json(os.path.join(legacy, "main.materials.json"), definitions)

'''
src = src[:start] + NEW_METHOD + src[end:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print()
print("block added        :", "CS1_TERRAIN_MATERIAL" in src)
print("copy fn            :", "def copy_working_terrain_textures" in src)
print("missing textures   :", missing if missing else "none")
