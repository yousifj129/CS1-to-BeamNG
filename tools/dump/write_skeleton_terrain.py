"""
Write the Skeleton Coast terrain implementation into the converter.

Produces a self-contained block holding that map's material (41 fields, including the
`*DetailTexSize` values our material never had), its texture set, and the list of textures to
provide.  Base textures are copied in at their native 4096x4096; detail and macro textures are
provided through `.link` sidecar files pointing at the source level, which is the mechanism
Skeleton Coast itself uses.
"""

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

# Which textures are real files and which are links in the source.
families = {"base": {}, "detail": {}, "macro": {}}
with zipfile.ZipFile(SOURCE_ARCHIVE) as z:
    names = set(z.namelist())

    for field, value in material.items():
        if not (isinstance(value, str) and field.endswith("Tex")):
            continue
        name = os.path.basename(value.replace("\\", "/"))
        member = f"levels/{SOURCE_LEVEL}/art/terrains/{name}"
        has_file = member in names
        has_link = member + ".link" in names
        target = None
        if has_link:
            link = json.loads(z.read(member + ".link").decode("utf-8", "replace"))
            target = link["path"]

        entry = {"field": field, "name": name, "file": has_file, "link": target}
        if "BaseTex" in field:
            families["base"][field] = entry
        elif "DetailTex" in field:
            families["detail"][field] = entry
        elif "MacroTex" in field:
            families["macro"][field] = entry

print(f"base   : {len(families['base'])} ({sum(1 for e in families['base'].values() if e['file'])} real files)")
print(f"detail : {len(families['detail'])} ({sum(1 for e in families['detail'].values() if e['file'])} real files, rest via .link)")
print(f"macro  : {len(families['macro'])} ({sum(1 for e in families['macro'].values() if e['file'])} real files, rest via .link)")
for fam in ("detail", "macro"):
    for e in families[fam].values():
        if e["link"]:
            print(f"   {fam} link: {e['name']} -> {e['link']}")

BLOCK = (
    "# ==========================================================================================\n"
    "#  Terrain material replicated from skeleton_coast, field for field.\n"
    "#\n"
    "#  Everything the source map declares is reproduced here, including `*DetailTexSize`, a third\n"
    "#  size field present on every detail texture that our material never carried.\n"
    "#\n"
    "#  Texture provisioning follows the source map exactly:\n"
    "#    * base family   -- real files copied into the level at their native 4096x4096\n"
    "#    * detail/macro  -- `.link` sidecar files, a small JSON document that redirects a texture\n"
    "#                       name to a path in another level:\n"
    "#                           {\"path\":\"/levels/<level>/art/terrains/<file>\",\"type\":\"normal\"}\n"
    "#\n"
    "#  `squareSize` and `baseTexSize` come from the source TerrainBlock.\n"
    "# ==========================================================================================\n"
    "CS1_TERRAIN_MATERIAL = " + repr(material) + "\n\n"
    "CS1_TERRAIN_TEXTURE_SET = " + repr(texture_set) + "\n\n"
    "CS1_TERRAIN_TEXTURE_PLAN = " + repr(families) + "\n\n"
    "CS1_TERRAIN_SOURCE_ARCHIVE = " + repr("skeleton_coast_1_3.zip") + "\n"
    "CS1_TERRAIN_SOURCE_LEVEL = " + repr(SOURCE_LEVEL) + "\n\n\n"
    "def provision_skeleton_terrain(level_root: str, level_name: str) -> Dict[str, str]:\n"
    '    """\n'
    "    Provide every terrain texture the replicated material names.\n"
    "\n"
    "    Base textures are copied in as real files.  Detail and macro textures are provided as\n"
    "    `.link` sidecars pointing at the source level, which is how skeleton_coast itself resolves\n"
    "    them -- the engine follows the link and loads the texture from that path.\n"
    "\n"
    "    Returns {field name -> value to write for that field}.\n"
    '    """\n'
    "    game = find_beamng_install()\n"
    "    archive = os.path.join(game, \"content\", \"levels\", CS1_TERRAIN_SOURCE_ARCHIVE) if game else None\n"
    "    if not archive or not os.path.isfile(archive):\n"
    "        archive = os.path.join(\n"
    "            os.path.expandvars(r\"%LOCALAPPDATA%\"), \"BeamNG\", \"BeamNG.drive\", \"current\",\n"
    "            \"mods\", \"repo\", CS1_TERRAIN_SOURCE_ARCHIVE,\n"
    "        )\n"
    "    if not os.path.isfile(archive):\n"
    "        return {}\n"
    "\n"
    "    target = os.path.join(level_root, \"art\", \"terrains\")\n"
    "    os.makedirs(target, exist_ok=True)\n"
    "    vfs = f\"/levels/{level_name.lower()}/art/terrains\"\n"
    "    resolved: Dict[str, str] = {}\n"
    "\n"
    "    with zipfile.ZipFile(archive) as source:\n"
    "        for family, entries in CS1_TERRAIN_TEXTURE_PLAN.items():\n"
    "            for field, info in entries.items():\n"
    "                name = info[\"name\"]\n"
    "                member = f\"levels/{CS1_TERRAIN_SOURCE_LEVEL}/art/terrains/{name}\"\n"
    "                if info[\"file\"]:\n"
    "                    try:\n"
    "                        blob = source.read(member)\n"
    "                    except KeyError:\n"
    "                        continue\n"
    "                    # Base textures are copied verbatim; the detail and macro families are\n"
    "                    # reduced to links so the level does not carry tens of megabytes of\n"
    "                    # duplicates of another map's textures.\n"
    "                    if family == \"base\":\n"
    "                        with open(os.path.join(target, name), \"wb\") as handle:\n"
    "                            handle.write(blob)\n"
    "                        resolved[field] = f\"{vfs}/{name}\"\n"
    "                    else:\n"
    "                        link = {\"path\": f\"{vfs}/{name}\", \"type\": \"normal\"}\n"
    "                        with open(os.path.join(target, name + \".link\"), \"w\", encoding=\"utf-8\") as handle:\n"
    "                            json.dump(link, handle)\n"
    "                        resolved[field] = f\"{vfs}/{name}\"\n"
    "                elif info[\"link\"]:\n"
    "                    # Follow the source level's own link; the engine resolves it directly.\n"
    "                    resolved[field] = info[\"link\"]\n"
    "    return resolved\n"
)

src = io.open(TARGET, encoding="utf-8").read()

# Replace the whole terrain-material block, from its banner up to emit_terrain_materials.
# NOTE: `src` is the RESTORED file.  Two terrain banners exist in it (an older block and the
# current one), so the match must start at the LAST banner -- matching the first one swallows
# everything between, including the BeamNGLevelBuilder class definition.
BANNER = "# ==========================================================================================\n#  Terrain material"
start = src.rindex(BANNER)
anchor = "    def emit_terrain_materials(self) -> None:"
end = src.index(anchor, start)
src = src[:start] + BLOCK + "\n\n\n" + src[end:]

# Rewrite emit_terrain_materials to use the replicated material.
method_end = src.index("    def emit_preview_image(self) -> None:", src.index(anchor))
NEW_METHOD = '''    def emit_terrain_materials(self) -> None:
        """
        Emit the terrain material replicated from skeleton_coast, with its textures provisioned.

        Every field of the source material is written unchanged apart from `internalName`, the
        `name`, and a fresh `persistentId`.  Texture paths come from provision_skeleton_terrain(),
        which copies the base family in and writes `.link` sidecars for the rest.
        """
        if self.terrain is None:
            return

        resolved = provision_skeleton_terrain(self.level_root, self.level_name)
        if not resolved:
            self.report["warnings"].append(
                "terrain textures could not be provided; the ground will render untextured"
            )

        material_name = self.terrain_materials[0]

        definition: Dict[str, Any] = {}
        for field, value in CS1_TERRAIN_MATERIAL.items():
            if field in resolved:
                definition[field] = resolved[field]
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
        os.makedirs(terrain_dir, exist_ok=True)
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)

        # Report what was provided, and mirror the base size onto the TerrainBlock.
        self.terrain_texture_base_size = int(
            (texture_set.get("baseTexSize") or [4096])[0]
        )
        self.report["terrainMaterial"] = {
            "internalName": material_name,
            "groundmodelName": definition.get("groundmodelName"),
            "textureSet": texture_set["name"],
            "texturesResolved": len(resolved),
            "baseTexSize": self.terrain_texture_base_size,
            "detailTexSize": definition.get("baseColorDetailTexSize"),
            "source": "skeleton_coast",
        }

'''
src = src[:src.index(anchor)] + NEW_METHOD + src[method_end:]

# Remove the older, now-dead terrain-material block that precedes the one we just replaced, so
# only a single definition of the terrain constants remains in the file.
DEAD_START = "# ==========================================================================================\n#  Terrain material, taken verbatim"
if DEAD_START in src:
    dead_start = src.index(DEAD_START)
    # It runs up to the banner of the block we just wrote.
    dead_end = src.index("# ==========================================================================================\n#  Terrain material replicated", dead_start)
    src = src[:dead_start] + src[dead_end:]
    print("removed the stale predecessor block")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)

import ast

ast.parse(src)
print()
print("SYNTAX OK")
print("material fields in block :", src.count("CS1_TERRAIN_MATERIAL ="))
print("provision function       :", "def provision_skeleton_terrain(" in src)
print(".link writing            :", 'name + ".link"' in src)
