"""
Replicate Skeleton Coast's terrain setup exactly.

It ships `.link` sidecar files beside the terrain material -- small text files that the engine
follows to locate a texture.  Nothing in our level uses that mechanism; we write absolute VFS paths
instead.  This reads the `.link` format, the material, the texture set, the TerrainBlock and the
terrain.json, so all of them can be reproduced field for field.
"""

import json
import os
import re
import struct
import zipfile

REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")
ARCHIVE = os.path.join(REPO_MODS, "skeleton_coast_1_3.zip")
LEVEL = "skeleton_coast"
PREFIX = f"levels/{LEVEL}/"

z = zipfile.ZipFile(ARCHIVE)

print("=" * 100)
print("1. WHAT A .link FILE CONTAINS")
print("=" * 100)
for name in ("t_asphalt_02_b.png.link", "t_macro_clumpy_b.png.link", "t_sand_b.png.link",
             "t_terrain_base_asphalt_b.png.link"):
    member = PREFIX + "art/terrains/" + name
    try:
        raw = z.read(member)
    except KeyError:
        continue
    print(f"\n   {name}  ({len(raw)} bytes)")
    print(f"      raw  : {raw[:200]!r}")
    # Try common encodings.
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            if enc != "latin-1" or True:
                print(f"      {enc:<7}: {text.strip()[:160]!r}")
        except Exception:
            pass

print()
print("=" * 100)
print("2. THE TERRAIN MATERIAL FILE")
print("=" * 100)
data = json.loads(z.read(PREFIX + "art/terrains/main.materials.json").decode("utf-8", "replace"))
sets = [v for v in data.values() if isinstance(v, dict) and v.get("class") == "TerrainMaterialTextureSet"]
mats = [v for v in data.values() if isinstance(v, dict) and v.get("class") == "TerrainMaterial"]
print(f"   texture sets: {len(sets)}   materials: {len(mats)}")
for s in sets:
    print("   set:", json.dumps(s))
print()
print("   first material, every field:")
first = mats[0]
for k in sorted(first):
    print(f"      {k:<28} {first[k]!r}")

print()
print("=" * 100)
print("3. TerrainBlock AND terrain.json")
print("=" * 100)
decoder = json.JSONDecoder()
for e in z.infolist():
    low = e.filename.lower()
    if not low.startswith(PREFIX) or not low.endswith("items.level.json"):
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
        if obj.get("class") == "TerrainBlock":
            print(f"   in {e.filename[len(PREFIX):]}")
            for k in sorted(obj):
                print(f"      {k:<24} {obj[k]!r}")

for e in z.infolist():
    if e.filename.lower().endswith(".terrain.json") and e.filename.lower().startswith(PREFIX):
        print(f"\n   {e.filename[len(PREFIX):]}")
        for k in sorted(json.loads(z.read(e).decode("utf-8", "replace"))):
            print(f"      {k:<20} {json.loads(z.read(e).decode('utf-8','replace'))[k]!r}")
        break

print()
print("=" * 100)
print("4. .ter STRUCTURE")
print("=" * 100)
for e in z.infolist():
    if e.filename.lower().endswith(".ter") and e.filename.lower().startswith(PREFIX):
        raw = z.read(e)
        version = raw[0]
        size = struct.unpack_from("<I", raw, 1)[0]
        n = size * size
        count_off = 5 + n * 2 + n + n
        print(f"   {e.filename[len(PREFIX):]}  version={version} size={size} bytes={len(raw)}")
        if count_off + 4 <= len(raw):
            cnt = struct.unpack_from("<I", raw, count_off)[0]
            off = count_off + 4
            names = []
            for _ in range(cnt):
                end = raw.index(b"\x00", off)
                names.append(raw[off:end].decode("utf-8", "replace"))
                off = end + 1
            print(f"      materials ({cnt}): {names[:6]}")
            print(f"      trailing: {len(raw) - off}")
        else:
            print(f"      count offset {count_off} beyond file -- layout differs")
        break

z.close()
