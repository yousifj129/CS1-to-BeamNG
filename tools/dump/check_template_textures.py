"""Confirm the full texture set for a template-based grass and asphalt v1.5 material."""

import os
import zipfile

TEMPLATE = r"D:\SteamLibrary\steamapps\common\BeamNG.drive\content\levels\template.zip"

NEEDED = {
    "grass": [
        "t_terrain_base_grass_b.png", "t_terrain_base_grass_nm.png",
        "t_terrain_base_grass_r.png", "t_terrain_base_grass_ao.png",
        "t_terrain_base_grass_h.png",
        "t_grass1_b.png", "t_grass1_nm.png", "t_grass1_r.png",
        "t_grass1_ao.png", "t_grass1_h.png",
        "t_macro_grass_b.png", "t_macro_grass_nm.png", "t_macro_grass_r.png",
        "t_macro_grass_ao.png", "t_macro_grass_h.png",
    ],
    "asphalt": [
        "t_terrain_base_asphalt_b.png", "t_terrain_base_asphalt_nm.png",
        "t_terrain_base_asphalt_r.png", "t_terrain_base_asphalt_ao.png",
        "t_terrain_base_asphalt_h.png",
        "t_asphalt_02_b.png", "t_asphalt_02_nm.png", "t_asphalt_02_r.png",
        "t_asphalt_02_ao.png", "t_asphalt_02_h.png",
        "t_macro_asphalt_b.png", "t_macro_asphalt_nm.png", "t_macro_asphalt_r.png",
        "t_macro_asphalt_ao.png", "t_macro_asphalt_h.png",
    ],
    "concrete": [
        "t_terrain_base_concrete_b.png", "t_terrain_base_concrete_nm.png",
        "t_terrain_base_concrete_r.png", "t_terrain_base_concrete_ao.png",
        "t_terrain_base_concrete_h.png",
        "t_macro_concrete_b.png", "t_macro_concrete_nm.png", "t_macro_concrete_r.png",
    ],
}

with zipfile.ZipFile(TEMPLATE) as archive:
    available = {
        os.path.basename(e.filename)
        for e in archive.infolist()
        if "art/terrains/" in e.filename
    }
    print(f"template terrain textures: {len(available)}")
    print()
    for group, names in NEEDED.items():
        print(f"--- {group}")
        missing = [n for n in names if n not in available]
        present = [n for n in names if n in available]
        print(f"    present: {len(present)}/{len(names)}")
        if missing:
            for name in missing:
                print(f"    MISSING: {name}")
        print()

    print("all template base/macro texture names (base + macro only):")
    for name in sorted(n for n in available if n.startswith(("t_terrain_base", "t_macro"))):
        print(f"    {name}")
