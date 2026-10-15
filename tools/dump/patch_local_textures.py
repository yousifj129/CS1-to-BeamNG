"""Copy the template grass textures into the mod and point the terrain material at them."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
s = io.open(TARGET, encoding="utf-8").read()

# ---- 1. helper that copies the texture set out of the game's own content ---------------
HELPER = '''def copy_terrain_textures(destination_dir: str) -> Dict[str, str]:
    """
    Copy the shared grass texture set out of the game's `levels/template` archive into the level.

    This is what working third-party maps do, and it is the reason referencing those textures by
    path never worked.  A level's terrain material can only resolve textures that live inside the
    level itself -- every shipped third-party level ships its own copies under
    `levels/<level>/art/terrains/` and points at them locally:

        baseColorBaseTex = /levels/grille_mbwr_city/art/terrains/east_coast_usa_t_dirt_rocky_b.png

    Referencing `/levels/template/...` or `/assets/materials/...` from a different level produced:

        E|TerrainCellMaterial| Missing Terrain texture: /

    for every slot, no textures packed, and flat grey ground.

    Returns a mapping of base filename -> in-level path, so the material can point at the copies.
    """
    import zipfile

    sources = [
        ("content/levels/template.zip", "levels/template/art/terrains/"),
        ("content/assets/materials/terrain.zip", "assets/materials/terrain/"),
    ]

    wanted = [
        "t_terrain_base_grass_b.png", "t_terrain_base_grass_nm.png",
        "t_terrain_base_grass_r.png", "t_terrain_base_grass_ao.png",
        "t_terrain_base_grass_h.png",
        "t_ind_grass_b.png", "t_ind_grass_nm.png", "t_ind_grass_r.png",
        "t_ind_grass_ao.png", "t_ind_grass_h.png",
        "t_macro_clumpy_b.png", "t_macro_clumpy_nm.png", "t_macro_clumpy_r.png",
        "t_macro_clumpy_ao.png", "t_macro_clumpy_h.png",
    ]

    game_root = os.environ.get("BEAMNG_PATH") or r"D:\\SteamLibrary\\steamapps\\common\\BeamNG.drive"
    os.makedirs(destination_dir, exist_ok=True)

    copied: Dict[str, str] = {}
    remaining = set(wanted)

    for archive_rel, prefix in sources:
        if not remaining:
            break
        archive_path = os.path.join(game_root, archive_rel.replace("/", os.sep))
        if not os.path.isfile(archive_path):
            continue
        with zipfile.ZipFile(archive_path) as archive:
            index = {}
            for entry in archive.infolist():
                if entry.filename.startswith(prefix) and entry.filename.endswith(".png"):
                    index[os.path.basename(entry.filename)] = entry
            for name in list(remaining):
                entry = index.get(name)
                if entry is None:
                    continue
                target = os.path.join(destination_dir, name)
                with archive.open(entry) as source, open(target, "wb") as handle:
                    handle.write(source.read())
                copied[name] = target
                remaining.discard(name)

    return copied


'''

anchor = "def emit_terrain_materials(self) -> None:"
if anchor not in s:
    raise SystemExit("emit_terrain_materials anchor not found")
# Insert the helper just before `class BeamNGLevelBuilder`.
class_at = s.index("class BeamNGLevelBuilder")
s = s[:class_at] + HELPER + s[class_at:]

# ---- 2. material now points at the copied, in-level textures ---------------------------
OLD_PATHS = '''        base = "/levels/template/art/terrains"
        grass = "/assets/materials/terrain/grass/ind_grass"
        macro = "/assets/materials/terrain/soil/macro_clumply"
        material_name = self.terrain_materials[0]
'''
NEW_PATHS = '''        material_name = self.terrain_materials[0]

        # Textures must live INSIDE the level; a level cannot resolve another level's or the
        # game's asset textures by path.  Copy the shared grass set in, then reference the copies
        # with forward slashes (the engine also accepts backslashes, as some maps use).
        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)
        copied = copy_terrain_textures(terrain_dir)
        for name, path in sorted(copied.items()):
            self.report["files"].append(os.path.relpath(path, self.mod_root))

        if not copied:
            self.report["warnings"].append(
                "no terrain textures could be copied from the game content; the ground will "
                "render untextured"
            )

        vfs = f"/levels/{self.level_name.lower()}/art/terrains"
        base = grass = macro = vfs
'''
if OLD_PATHS not in s:
    raise SystemExit("terrain texture path anchor not found")
s = s.replace(OLD_PATHS, NEW_PATHS, 1)

# Replace each /levels/template/... and /assets/... reference with the local copy path.
s = s.replace('f"{base}/t_terrain_base_grass_b.png"', 'f"{vfs}/t_terrain_base_grass_b.png"')
s = s.replace('f"{base}/t_terrain_base_grass_nm.png"', 'f"{vfs}/t_terrain_base_grass_nm.png"')
s = s.replace('f"{base}/t_terrain_base_grass_r.png"', 'f"{vfs}/t_terrain_base_grass_r.png"')
s = s.replace('f"{base}/t_terrain_base_grass_ao.png"', 'f"{vfs}/t_terrain_base_grass_ao.png"')
s = s.replace('f"{base}/t_terrain_base_grass_h.png"', 'f"{vfs}/t_terrain_base_grass_h.png"')
s = s.replace('f"{grass}/t_ind_grass_b.png"', 'f"{vfs}/t_ind_grass_b.png"')
s = s.replace('f"{grass}/t_ind_grass_nm.png"', 'f"{vfs}/t_ind_grass_nm.png"')
s = s.replace('f"{grass}/t_ind_grass_r.png"', 'f"{vfs}/t_ind_grass_r.png"')
s = s.replace('f"{grass}/t_ind_grass_ao.png"', 'f"{vfs}/t_ind_grass_ao.png"')
s = s.replace('f"{grass}/t_ind_grass_h.png"', 'f"{vfs}/t_ind_grass_h.png"')
s = s.replace('f"{macro}/t_macro_clumpy_b.png"', 'f"{vfs}/t_macro_clumpy_b.png"')
s = s.replace('f"{macro}/t_macro_clumpy_nm.png"', 'f"{vfs}/t_macro_clumpy_nm.png"')
s = s.replace('f"{macro}/t_macro_clumpy_r.png"', 'f"{vfs}/t_macro_clumpy_r.png"')
s = s.replace('f"{macro}/t_macro_clumpy_ao.png"', 'f"{vfs}/t_macro_clumpy_ao.png"')
s = s.replace('f"{macro}/t_macro_clumpy_h.png"', 'f"{vfs}/t_macro_clumpy_h.png"')

# The old target dir variable is now unused; keep the write loop but drop the duplicate mkdir.
s = s.replace(
    '''        for folder in ("terrains", "terrain"):
            target = os.path.join(self.level_root, "art", folder)
            os.makedirs(target, exist_ok=True)
            self.write_json(os.path.join(target, "main.materials.json"), definitions)''',
    '''        # art/terrains/ is the modern location; art/terrain/ is still read by some paths and
        # also needs the textures beside it, so the whole folder is mirrored.
        legacy = os.path.join(self.level_root, "art", "terrain")
        os.makedirs(legacy, exist_ok=True)
        for name, path in copied.items():
            legacy_path = os.path.join(legacy, name)
            with open(path, "rb") as src, open(legacy_path, "wb") as dst:
                dst.write(src.read())
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)
        self.write_json(os.path.join(legacy, "main.materials.json"), definitions)''',
    1,
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(s)
print("helper added            :", "def copy_terrain_textures(" in s)
print("local vfs paths         :", 'vfs = f"/levels/{self.level_name.lower()}/art/terrains"' in s)
print("template refs remaining :", s.count('/levels/template/art/terrains'))
print("assets refs remaining   :", s.count('/assets/materials/terrain'))
