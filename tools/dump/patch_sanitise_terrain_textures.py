"""
Remove the two remaining hazards from the terrain texture references.

Both were inherited by copying grille_mbwr_city verbatim, which was the right instinct but carries
its quirks:

1. The `#` character in filenames.  grille ships files literally named `#base_ao.png`,
   `#5d5544.png` and so on.  In URL and virtual-filesystem handling `#` begins a fragment, so a
   lookup by name can legitimately fail to resolve even though the file is mounted and present.
   The files are renamed to plain alphanumeric names.

2. A backslash used as a separator before the filename (`art/terrains\\name.png`).  The engine
   tolerates it in some builds, but it is not a path separator on any platform BeamNG targets.
   Forward slashes are used throughout.

The material is otherwise untouched: same structure, same texture set, same strength and distance
values.
"""

import ast
import io
import json
import os
import shutil
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")

BLOCK_START = "# ==========================================================================================\n#  Terrain material copied VERBATIM from grille_mbwr_city"
src = io.open(TARGET, encoding="utf-8").read()
start = src.index(BLOCK_START)
end = src.index("def copy_grille_terrain(")
# Keep through the end of that function.
fn_start = end
fn_end = src.index("\n\n\n", src.index("return copied", fn_start))

NEW = '''# ==========================================================================================
#  Terrain material taken from grille_mbwr_city, a working third-party city map, then cleaned of
#  the two quirks it carries:
#
#    * its texture files are named with a leading '#' (`#base_ao.png`).  In URL and virtual-
#      filesystem handling '#' begins a fragment, so a name lookup can fail to resolve even though
#      the file is mounted and present.  Files are renamed to plain alphanumeric names here.
#    * one path uses a backslash as the separator before the filename.  Forward slashes are used.
#
#  Everything else -- structure, texture set, strengths, distances -- is unchanged.
# ==========================================================================================
CS1_TERRAIN_TEXTURE_MEMBERS = {
    # source name inside grille_mbwr_city  ->  name used in this level
    "#base_ao.png": "terrain_base_ao.png",
    "#base_h.png": "terrain_base_h.png",
    "#base_nm.png": "terrain_base_nm.png",
    "#5d5544.png": "terrain_base_b.png",
    "#dirt_r.png": "terrain_base_r.png",
    "east_coast_usa_t_dirt_rocky_ao.png": "terrain_detail_ao.png",
    "east_coast_usa_t_dirt_rocky_b.png": "terrain_detail_b.png",
    "east_coast_usa_t_dirt_rocky_h.png": "terrain_detail_h.png",
    "east_coast_usa_t_dirt_rocky_nm.png": "terrain_detail_nm.png",
    "east_coast_usa_t_dirt_rocky_r.png": "terrain_detail_r.png",
    "east_coast_usa_t_macro_holes_ao.png": "terrain_macro_ao.png",
    "east_coast_usa_t_macro_holes_b.png": "terrain_macro_b.png",
    "east_coast_usa_t_macro_holes_h.png": "terrain_macro_h.png",
    "east_coast_usa_t_macro_holes_nm.png": "terrain_macro_nm.png",
    "east_coast_usa_t_macro_holes_r.png": "terrain_macro_r.png",
}

CS1_TERRAIN_SOURCE_LEVEL = "grille_mbwr_city"


def copy_grille_terrain(level_root: str, level_name: str) -> Dict[str, str]:
    """
    Copy the source map's terrain textures in under sanitised names.

    Returns {source filename -> in-level path}.  The bytes are unchanged; only the names differ,
    so the `#` cannot interfere with resolution.
    """
    game = find_beamng_install()
    archive = (
        os.path.join(game, "content", "levels", "grille_mbwr_city.zip") if game else None
    )
    if not archive or not os.path.isfile(archive):
        archive = os.path.join(
            os.path.expandvars(r"%LOCALAPPDATA%"), "BeamNG", "BeamNG.drive", "current",
            "mods", "repo", "grille_mbwr_city.zip",
        )
    if not os.path.isfile(archive):
        return {}

    target = os.path.join(level_root, "art", "terrains")
    os.makedirs(target, exist_ok=True)
    copied: Dict[str, str] = {}

    with zipfile.ZipFile(archive) as source:
        for src_name, dst_name in CS1_TERRAIN_TEXTURE_MEMBERS.items():
            member = f"levels/{CS1_TERRAIN_SOURCE_LEVEL}/art/terrains/{src_name}"
            try:
                blob = source.read(member)
            except KeyError:
                continue
            with open(os.path.join(target, dst_name), "wb") as handle:
                handle.write(blob)
            copied[src_name] = f"/levels/{level_name.lower()}/art/terrains/{dst_name}"

    return copied'''

src = src[:start] + NEW + src[fn_end:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("renamed members table:", "CS1_TERRAIN_TEXTURE_MEMBERS" in src)
