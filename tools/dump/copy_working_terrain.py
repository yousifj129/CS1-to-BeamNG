"""
Copy a fully working level's terrain material and textures verbatim.

The user's instruction is to do for the terrain what worked for the roads materials: take a known
good one rather than invent.  grille_mbwr_city is a shipped third-party city map whose ground
renders, and it is small and self-contained.

Its form (measured):

    TerrainMaterialTextureSet   baseTexSize [1024,1024]  detail [1024,1024]  macro [1024,1024]
    TerrainMaterial             *BaseTex / *DetailTex / *MacroTex are ALL LOCAL to the level,
                                referenced with a backslash before the filename
    local PNGs                  89 files, 1024x1024

So the material, the texture set and the texture files are copied here exactly, with only
`internalName` (and the set's name) changed to avoid colliding with the original level.  Every
texture path keeps the working level's own form, including the backslash.

Also added, taken from a working TerrainBlock: `baseTexSize` and `screenError` 64.  Every working
level's TerrainBlock carries fields that ours did not, and the terrain material is resolved
through that block.
"""

import io
import json
import os
import re
import shutil
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")
SOURCE = os.path.join(REPO_MODS, "grille_mbwr_city.zip")
SOURCE_LEVEL = "grille_mbwr_city"

# ---- read the working material, its set, and every texture it names ---------------------
with zipfile.ZipFile(SOURCE) as z:
    mat_member = next(
        e.filename for e in z.infolist()
        if re.search(r"art/terrains?/main\.materials\.json$", e.filename, re.I)
    )
    data = json.loads(z.read(mat_member).decode("utf-8", "replace"))
    material = next(v for v in data.values() if v.get("class") == "TerrainMaterial")
    texture_set = next(v for v in data.values() if v.get("class") == "TerrainMaterialTextureSet")

    # Every texture the material names, resolved to a member of the source level.
    textures = {}
    for field, value in material.items():
        if not (isinstance(value, str) and field.endswith("Tex")):
            continue
        normalised = value.replace("\\", "/")
        base = os.path.basename(normalised)
        member = f"levels/{SOURCE_LEVEL}/art/terrains/{base}"
        try:
            textures[base] = z.read(member)
        except KeyError:
            pass

print(f"source material : {material.get('internalName')} ({len(material)} fields)")
print(f"texture set     : {texture_set.get('name')} base={texture_set.get('baseTexSize')}")
print(f"textures found  : {len(textures)}")
for name in sorted(textures):
    print(f"   {name}")

missing = [
    os.path.basename(v.replace("\\", "/"))
    for k, v in material.items()
    if isinstance(v, str) and k.endswith("Tex")
    and os.path.basename(v.replace("\\", "/")) not in textures
]
print(f"unresolved      : {missing or 'NONE'}")

# ---- emit into the converter -----------------------------------------------------------
BLOCK = (
    "# ==========================================================================================\n"
    "#  Terrain material copied VERBATIM from grille_mbwr_city, a working third-party city map.\n"
    "#\n"
    "#  The same approach that fixed the road materials: rather than invent a material, take one\n"
    "#  from a level whose ground demonstrably renders.  The material, its TerrainMaterialTextureSet\n"
    "#  and all of its texture files are reproduced here exactly; only the material's internal name\n"
    "#  and the set's name are changed so they cannot collide with the original level.\n"
    "#\n"
    "#  Texture paths keep the source level's own form, including the backslash separator before\n"
    "#  the filename, because that is the form the engine resolves for that map.\n"
    "# ==========================================================================================\n"
    "CS1_TERRAIN_MATERIAL = " + repr(material) + "\n\n"
    "CS1_TERRAIN_TEXTURE_SET = " + repr(texture_set) + "\n\n"
    "CS1_TERRAIN_TEXTURE_MEMBERS = " + repr(
        {name: f"levels/{SOURCE_LEVEL}/art/terrains/{name}" for name in sorted(textures)}
    ) + "\n\n\n"
    "def copy_grille_terrain(level_root: str, level_name: str) -> Dict[str, str]:\n"
    '    """\n'
    "    Copy the source map's terrain textures in, and return old-path -> new-path for rewriting.\n"
    "\n"
    "    Nothing is generated or resized: the bytes are the ones the working map ships.\n"
    '    """\n'
    "    game = find_beamng_install()\n"
    "    archive = os.path.join(game, \"content\", \"levels\", \"grille_mbwr_city.zip\") if game else None\n"
    "    if not archive or not os.path.isfile(archive):\n"
    "        archive = os.path.join(\n"
    "            os.path.expandvars(r\"%LOCALAPPDATA%\"), \"BeamNG\", \"BeamNG.drive\", \"current\",\n"
    "            \"mods\", \"repo\", \"grille_mbwr_city.zip\",\n"
    "        )\n"
    "    if not os.path.isfile(archive):\n"
    "        return {}\n"
    "\n"
    "    target = os.path.join(level_root, \"art\", \"terrains\")\n"
    "    os.makedirs(target, exist_ok=True)\n"
    "    copied: Dict[str, str] = {}\n"
    "    with zipfile.ZipFile(archive) as src:\n"
    "        for name, member in CS1_TERRAIN_TEXTURE_MEMBERS.items():\n"
    "            try:\n"
    "                blob = src.read(member)\n"
    "            except KeyError:\n"
    "                continue\n"
    "            with open(os.path.join(target, name), \"wb\") as handle:\n"
    "                handle.write(blob)\n"
    "            copied[name] = f\"/levels/{level_name.lower()}/art/terrains/{name}\"\n"
    "    return copied\n"
)

anchor = "    def emit_terrain_materials(self) -> None:"
src2 = io.open(TARGET, encoding="utf-8").read()
class_at = src2.index("class BeamNGLevelBuilder")
src2 = src2[:class_at] + BLOCK + "\n\n" + src2[class_at:]

# Replace the method body with one that uses the copied material.
start = src2.index(anchor)
end = src2.index("    def emit_preview_image(self) -> None:", start)

METHOD = '''    def emit_terrain_materials(self) -> None:
        """
        Emit the working map's terrain material, with its own textures copied in beside it.

        `CS1_TERRAIN_MATERIAL` and `CS1_TERRAIN_TEXTURE_SET` come verbatim from grille_mbwr_city,
        a shipped map whose ground renders.  Only `internalName` and the set's name are changed.
        Every texture the material names is copied into this level, so the paths resolve exactly
        as they do in the level the material came from.
        """
        if self.terrain is None:
            return

        copied = copy_grille_terrain(self.level_root, self.level_name)
        for _name, path in sorted(copied.items()):
            self.report["files"].append(
                os.path.relpath(
                    os.path.join(self.level_root, "art", "terrains", _name), self.mod_root
                )
            )
        if not copied:
            self.report["warnings"].append(
                "no terrain textures could be copied; the ground will render untextured"
            )

        material_name = self.terrain_materials[0]
        vfs = f"/levels/{self.level_name.lower()}/art/terrains"

        definition: Dict[str, Any] = {}
        for field, value in CS1_TERRAIN_MATERIAL.items():
            if isinstance(value, str) and field.endswith("Tex"):
                # Keep the source form, including its backslash, but point at our copy.
                base = os.path.basename(value.replace("\\\\", "/"))
                if base in copied:
                    definition[field] = f"{vfs}\\\\{base}"
                else:
                    definition[field] = value
            else:
                definition[field] = value
        definition["internalName"] = material_name
        definition["name"] = material_name
        definition["persistentId"] = new_id()

        texture_set = dict(CS1_TERRAIN_TEXTURE_SET)
        texture_set["name"] = self.texture_set_name
        texture_set["persistentId"] = new_id()

        definitions = {
            f"{self.level_name}TerrainMaterialTextureSet": texture_set,
            f"{material_name}-{new_id()}": definition,
        }

        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)

        self.report["terrainMaterial"] = {
            "internalName": material_name,
            "groundmodelName": definition.get("groundmodelName"),
            "textureSet": texture_set["name"],
            "texturesCopied": len(copied),
            "sourceSetSizes": texture_set.get("baseTexSize"),
        }

'''

src2 = src2[:start] + METHOD + src2[end:]

# TerrainBlock gains the fields every working level carries.
src2 = src2.replace(
    '            "squareSize": self.terrain.square_size,',
    '            # Working levels carry these on the TerrainBlock; the material resolves through it.\n'
    '            "baseTexSize": self.terrain_texture_base_size,\n'
    '            "squareSize": self.terrain.square_size,',
    1,
)
src2 = src2.replace('"screenError": 16,', '"screenError": 64,', 1)
src2 = src2.replace(
    '        self.texture_set_name = f"{level_name}TerrainMaterialTextureSet"',
    '        self.texture_set_name = f"{level_name}TerrainMaterialTextureSet"\n'
    '        self.terrain_texture_base_size = 1024',
    1,
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src2)

import ast

try:
    ast.parse(src2)
    print()
    print("SYNTAX OK")
except SyntaxError as exc:
    print("SYNTAX ERROR line", exc.lineno)
    lines = src2.split("\n")
    for i in range(max(0, exc.lineno - 4), min(len(lines), exc.lineno + 3)):
        print(f"  {i + 1:>5}| {lines[i][:110]}")
    raise SystemExit(1)
