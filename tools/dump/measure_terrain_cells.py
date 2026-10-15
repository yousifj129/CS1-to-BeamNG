"""
Measure the error count per terrain cell, and find the smallest working material.

96 errors is suspiciously regular.  This counts the terrain cells BeamNG creates for each level's
grid, so the errors-per-cell can be derived -- that number says how many texture slots per cell the
engine is failing to fill, which identifies which family is missing.

It also lists, for every working map, exactly which `*Tex` families its first TerrainMaterial uses
and how large its texture set is, so a minimal known-good example can be identified.
"""

import collections
import json
import os
import struct
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")

MAPS = [
    ("MINE", os.path.join(REPO, "dist", "cs1_cannes.zip"), "levels/cannes/"),
    ("grille_mbwr_city", os.path.join(REPO_MODS, "grille_mbwr_city.zip"), "levels/grille_mbwr_city/"),
    ("polish_roads_v2", os.path.join(REPO_MODS, "polish_roads_repo.zip"), "levels/polish_roads_v2/"),
    ("Valo_City", os.path.join(REPO_MODS, "Valo_City.zip"), "levels/valo_city/"),
    ("Generic_City", os.path.join(REPO_MODS, "Generic_City.zip"), "levels/generic_city/"),
    ("autobahnvawriss", os.path.join(REPO_MODS, "autobahnvawriss.zip"), "levels/autobahnvawriss/"),
]

print("=" * 100)
print("TERRAIN GRID AND TEXTURE FAMILIES")
print("=" * 100)

for label, path, prefix in MAPS:
    if not os.path.isfile(path):
        print(f"\n{label}: archive not found")
        continue
    print(f"\n{label}")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()

        # grid size from the .ter
        for n in names:
            if not n.lower().endswith(".ter") or not n.lower().startswith(prefix.lower()):
                continue
            try:
                raw = z.read(n)
                grid = struct.unpack_from("<I", raw, 1)[0]
                print(f"   .ter grid      : {grid}  ({n.split('/')[-1]})")
            except Exception as exc:
                print(f"   .ter unreadable: {exc}")
            break

        # texture set + first material
        for n in names:
            low = n.lower()
            if not low.startswith(prefix.lower()) or "main.materials.json" not in low:
                continue
            if "art/terrain" not in low:
                continue
            try:
                data = json.loads(z.read(n).decode("utf-8", "replace"))
            except Exception:
                continue
            for v in data.values():
                if not isinstance(v, dict):
                    continue
                if v.get("class") == "TerrainMaterialTextureSet":
                    print(f"   texture set    : base={v.get('baseTexSize')} detail={v.get('detailTexSize')} macro={v.get('macroTexSize')}")
                elif v.get("class") == "TerrainMaterial":
                    families = collections.Counter()
                    for k, val in v.items():
                        if isinstance(val, str) and k.endswith("Tex"):
                            # base / detail / macro
                            for fam in ("Base", "Detail", "Macro"):
                                if fam in k:
                                    families[fam] += 1
                                    break
                    total = sum(families.values())
                    print(f"   first material : {v.get('internalName')!r} -> {total} textures {dict(families)}")
                    break
            break
