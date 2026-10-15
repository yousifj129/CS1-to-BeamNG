"""
Replace the grille-based terrain block with Skeleton Coast's, using exact line boundaries.

Line map of the current converter:
    1468  CS1_TERRAIN_MATERIAL (the older, unused block)
    1847  banner of the grille block
    1858  CS1_TERRAIN_TEXTURE_MEMBERS
    1880  def copy_grille_terrain
    1917  class BeamNGLevelBuilder          <- must be preserved
    2737  def emit_terrain_materials
    2802  def emit_preview_image

The block occupies lines 1847..1916 inclusive.  Operating on line numbers avoids the index-slicing
that previously swallowed the class definition.
"""

import ast
import io
import json
import os
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")
SOURCE_ARCHIVE = os.path.join(REPO_MODS, "skeleton_coast_1_3.zip")
SOURCE_LEVEL = "skeleton_coast"

data = json.load(open(os.path.join(REPO, "build", "skeleton_material.json"), encoding="utf-8"))
material = data["material"]
texture_set = data["textureSet"]

families = {"base": {}, "detail": {}, "macro": {}}
with zipfile.ZipFile(SOURCE_ARCHIVE) as z:
    names = set(z.namelist())
    for field, value in material.items():
        if not (isinstance(value, str) and field.endswith("Tex")):
            continue
        name = os.path.basename(value.replace("\\", "/"))
        member = f"levels/{SOURCE_LEVEL}/art/terrains/{name}"
        target = None
        if member + ".link" in names:
            target = json.loads(z.read(member + ".link").decode("utf-8", "replace"))["path"]
        entry = {"name": name, "file": member in names, "link": target}
        for key in ("Base", "Detail", "Macro"):
            if key + "Tex" in field:
                families[key.lower()][field] = entry
                break

BLOCK = '''# ==========================================================================================
#  Terrain material replicated from skeleton_coast, field for field.
#
#  Every field the source material declares is reproduced, including `*DetailTexSize` -- a third
#  size field present on each detail texture that our material never carried, and the only
#  structural difference left between our terrain material and a working one.
#
#  Textures are provided exactly as the source map provides them:
#    * base family   real files, copied into the level at their native 4096x4096
#    * detail/macro  `.link` sidecar files, a small JSON document redirecting a texture name to a
#                    path in another level:
#                        {"path":"/levels/<level>/art/terrains/<file>","type":"normal"}
# ==========================================================================================
CS1_TERRAIN_MATERIAL = ''' + repr(material) + '''

CS1_TERRAIN_TEXTURE_SET = ''' + repr(texture_set) + '''

CS1_TERRAIN_TEXTURE_PLAN = ''' + repr(families) + '''

CS1_TERRAIN_SOURCE_ARCHIVE = "skeleton_coast_1_3.zip"
CS1_TERRAIN_SOURCE_LEVEL = "skeleton_coast"


def provision_skeleton_terrain(level_root: str, level_name: str) -> Dict[str, str]:
    """
    Provide every texture the replicated material names, and return {field -> value to write}.

    Base textures become real files inside the level.  Detail and macro textures become `.link`
    sidecars, which is how skeleton_coast resolves them: the engine follows the link and loads the
    texture from the referenced level.
    """
    game = find_beamng_install()
    archive = os.path.join(game, "content", "levels", CS1_TERRAIN_SOURCE_ARCHIVE) if game else None
    if not archive or not os.path.isfile(archive):
        archive = os.path.join(
            os.path.expandvars(r"%LOCALAPPDATA%"), "BeamNG", "BeamNG.drive", "current",
            "mods", "repo", CS1_TERRAIN_SOURCE_ARCHIVE,
        )
    if not os.path.isfile(archive):
        return {}

    target = os.path.join(level_root, "art", "terrains")
    os.makedirs(target, exist_ok=True)
    vfs = f"/levels/{level_name.lower()}/art/terrains"
    resolved: Dict[str, str] = {}

    with zipfile.ZipFile(archive) as source:
        for family, entries in CS1_TERRAIN_TEXTURE_PLAN.items():
            for field, info in entries.items():
                name = info["name"]
                member = f"levels/{CS1_TERRAIN_SOURCE_LEVEL}/art/terrains/{name}"

                if info["file"] and family == "base":
                    try:
                        blob = source.read(member)
                    except KeyError:
                        continue
                    with open(os.path.join(target, name), "wb") as handle:
                        handle.write(blob)
                    resolved[field] = f"{vfs}/{name}"
                elif info["file"]:
                    # A real file, but part of a large family: link to a copy instead of carrying
                    # tens of megabytes of another map's textures.
                    link = {"path": f"{vfs}/{name}", "type": "normal"}
                    with open(os.path.join(target, name + ".link"), "w", encoding="utf-8") as handle:
                        json.dump(link, handle)
                    resolved[field] = f"{vfs}/{name}"
                elif info["link"]:
                    # Follow the source level's own link; the engine resolves that path directly.
                    resolved[field] = info["link"]

    return resolved
'''

lines = io.open(TARGET, encoding="utf-8").read().split("\n")

# Locate the grille block banner and the class definition by line number.
banner = next(
    i for i, l in enumerate(lines)
    if l.startswith("# ===") and "terrain material taken from grille" in lines[i + 1].lower()
)
class_line = next(i for i, l in enumerate(lines) if l.startswith("class BeamNGLevelBuilder"))
print(f"block starts at line {banner + 1}, class at line {class_line + 1}")

lines = lines[:banner] + BLOCK.split("\n") + ["", ""] + lines[class_line:]

src = "\n".join(lines)

# Point the emitter at the new provisioning function and the new constant names.
src = src.replace("copied = copy_grille_terrain(self.level_root, self.level_name)",
                  "resolved = provision_skeleton_terrain(self.level_root, self.level_name)")
src = src.replace("if not copied:", "if not resolved:")
src = src.replace("CS1_TERRAIN_TEXTURE_MEMBERS.items()", "resolved.items()")
src = src.replace("CS1_TERRAIN_SOURCE_LEVEL}/art/terrains/{src_name}", "CS1_TERRAIN_SOURCE_LEVEL}/art/terrains/{src_name}")

# Rewrite the emitter body to use `resolved` directly.
src = src.replace(
    '''        material_name = self.terrain_materials[0]
        vfs = f"/levels/{self.level_name.lower()}/art/terrains"

        definition: Dict[str, Any] = {}
        for field, value in CS1_TERRAIN_MATERIAL.items():
            if isinstance(value, str) and field.endswith("Tex"):
                # `copied` maps the source filename (which may contain '#' and is preceded by a
                # backslash in the source file) to a clean forward-slash path in this level.
                base = os.path.basename(value.replace("\\\\", "/"))
                if base in copied:
                    definition[field] = copied[base]
                else:
                    definition[field] = value
            else:
                definition[field] = value''',
    '''        material_name = self.terrain_materials[0]

        definition: Dict[str, Any] = {}
        for field, value in CS1_TERRAIN_MATERIAL.items():
            definition[field] = resolved.get(field, value)''',
)
src = src.replace(
    '''        copied = copy_grille_terrain(self.level_root, self.level_name)
        for _name, path in sorted(copied.items()):
            self.report["files"].append(
                os.path.relpath(
                    os.path.join(self.level_root, "art", "terrains", _name), self.mod_root
                )
            )''',
    '''        resolved = provision_skeleton_terrain(self.level_root, self.level_name)
        for _name in sorted(resolved):
            self.report["files"].append(
                os.path.relpath(
                    os.path.join(self.level_root, "art", "terrains", _name), self.mod_root
                )
            )''',
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)

print("SYNTAX OK")
for name in ("class BeamNGLevelBuilder", "CS1_TERRAIN_MATERIAL =",
             "def provision_skeleton_terrain", "def emit_terrain_materials",
             "def emit_preview_image", "def copy_grille_terrain"):
    print(f"  {name:<34} x{src.count(name)}")
