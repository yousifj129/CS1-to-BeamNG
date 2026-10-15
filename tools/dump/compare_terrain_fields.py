"""
Full field-by-field comparison of our terrain setup against working maps.

Nothing is changed here.  Every TerrainBlock field and every material field in four working maps is
listed next to ours, so any missing or anomalous key is visible rather than inferred.
"""

import collections
import json
import os
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")

SOURCES = [
    ("MINE", os.path.join(REPO, "dist", "cs1_cannes.zip"), "levels/cannes/"),
    ("grille_mbwr_city", os.path.join(REPO_MODS, "grille_mbwr_city.zip"), "levels/grille_mbwr_city/"),
    ("polish_roads_v2", os.path.join(REPO_MODS, "polish_roads_repo.zip"), "levels/polish_roads_v2/"),
    ("Valo_City", os.path.join(REPO_MODS, "Valo_City.zip"), "levels/valo_city/"),
    ("Generic_City", os.path.join(REPO_MODS, "Generic_City.zip"), "levels/generic_city/"),
]


def read_items(z, prefix):
    decoder = json.JSONDecoder()
    for e in z.infolist():
        low = e.filename.lower()
        if not low.startswith(prefix.lower()) or not low.endswith("items.level.json"):
            continue
        if e.file_size > 8_000_000:
            continue
        try:
            text = z.read(e).decode("utf-8", "replace")
        except Exception:
            continue
        i = 0
        while i < len(text):
            while i < len(text) and text[i].isspace():
                i += 1
            if i >= len(text):
                break
            try:
                obj, i = decoder.raw_decode(text, i)
            except json.JSONDecodeError:
                break
            yield obj


print("=" * 108)
print("TERRAINBLOCK FIELDS")
print("=" * 108)

blocks = {}
for label, path, prefix in SOURCES:
    if not os.path.isfile(path):
        print(f"  {label}: archive not found")
        continue
    with zipfile.ZipFile(path) as z:
        for obj in read_items(z, prefix):
            if obj.get("class") == "TerrainBlock":
                blocks[label] = obj
                break

all_keys = collections.OrderedDict()
for b in blocks.values():
    for k in b:
        all_keys[k] = None

print(f"  {'field':<22}" + "".join(f"{lbl[:16]:<18}" for lbl in blocks))
print("  " + "-" * 104)
for key in all_keys:
    row = f"  {key:<22}"
    values = [blocks[lbl].get(key, "-") for lbl in blocks]
    for v in values:
        text = str(v)
        row += f"{text[:16]:<18}"
    print(row)

print()
print("=" * 108)
print("TERRAIN MATERIAL FIELDS")
print("=" * 108)

materials = {}
for label, path, prefix in SOURCES:
    if not os.path.isfile(path):
        continue
    with zipfile.ZipFile(path) as z:
        for e in z.infolist():
            low = e.filename.lower()
            if not low.startswith(prefix.lower()):
                continue
            if "art/terrains/main.materials.json" not in low and "art/terrain/main.materials.json" not in low:
                continue
            try:
                data = json.loads(z.read(e).decode("utf-8", "replace"))
            except Exception:
                continue
            for v in data.values():
                if isinstance(v, dict) and v.get("class") == "TerrainMaterial":
                    materials[label] = v
                    break
            break

all_mkeys = collections.OrderedDict()
for m in materials.values():
    for k in m:
        all_mkeys[k] = None

print(f"  {'field':<30}" + "".join(f"{lbl[:18]:<20}" for lbl in materials))
print("  " + "-" * 104)
for key in all_mkeys:
    row = f"  {key:<30}"
    for lbl in materials:
        v = materials[lbl].get(key, "-")
        if isinstance(v, str) and len(v) > 18:
            v = "..." + v[-15:]
        row += f"{str(v)[:18]:<20}"
    print(row)
