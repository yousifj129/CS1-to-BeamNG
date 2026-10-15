"""
Study a large working third-party map (polish_roads_v2) to learn the real conventions.

Prints:
  1. which level folder(s) it ships
  2. every items.level.json in the level, with the SimGroups it declares and the __parent values
     of its objects -- this is the authority on how roads are parented
  3. a full DecalRoad object, verbatim
  4. its terrain material file and the texture set, plus the textures' real pixel sizes
  5. how the TerrainBlock references the texture set
"""

import json
import os
import re
import struct
import zipfile
from collections import Counter, defaultdict

ARCHIVE = os.path.join(
    os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo",
    "polish_roads_repo.zip",
)

z = zipfile.ZipFile(ARCHIVE)

# ---- 1. which levels does it ship? -----------------------------------------------------
levels = defaultdict(int)
for e in z.infolist():
    m = re.match(r"levels/([^/]+)/", e.filename, re.I)
    if m:
        levels[m.group(1)] += 1

print("=" * 100)
print("1. LEVELS IN THE ARCHIVE")
print("=" * 100)
for name, count in sorted(levels.items(), key=lambda kv: -kv[1])[:10]:
    print(f"   {count:>7} files   levels/{name}/")

target = "polish_roads_v2" if "polish_roads_v2" in levels else max(levels, key=lambda k: levels[k])
print(f"\n   -> studying: levels/{target}/")

prefix = f"levels/{target}/"

# ---- 2. items.level.json structure ------------------------------------------------------
print()
print("=" * 100)
print("2. GROUP STRUCTURE (items.level.json files)")
print("=" * 100)

items = [e for e in z.infolist() if e.filename.lower().startswith(prefix.lower())
         and e.filename.lower().endswith("items.level.json")]

# Only look at the first N so a huge level does not dominate.
items.sort(key=lambda e: e.filename)
print(f"   total items.level.json files: {len(items)}")

def read_objects(entry):
    text = z.read(entry).decode("utf-8", "replace")
    decoder = json.JSONDecoder()
    out, i = [], 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        try:
            obj, i = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        out.append(obj)
    return out

shown = 0
for entry in items:
    objs = read_objects(entry)
    if not objs:
        continue
    classes = Counter(str(o.get("class")) for o in objs)
    groups = [o.get("name") for o in objs if o.get("class") == "SimGroup"]
    # Show files that declare groups, or that hold roads, plus the first few others.
    interesting = groups or any(c == "DecalRoad" for c in classes)
    if not interesting and shown > 6:
        continue
    rel = entry.filename[len(prefix):]
    print(f"\n   --- {rel}")
    if groups:
        print(f"       declares SimGroups: {groups}")
    parents = Counter(str(o.get("__parent")) for o in objs if o.get("class") != "SimGroup")
    if parents:
        print(f"       object __parent   : {dict(parents)}")
    print(f"       classes           : {dict(classes)}")
    shown += 1
    if shown > 18:
        print("\n   ... (truncated)")
        break

# ---- 3. a verbatim DecalRoad ------------------------------------------------------------
print()
print("=" * 100)
print("3. A VERBATIM DecalRoad FROM THIS LEVEL")
print("=" * 100)
found = 0
for entry in items:
    for obj in read_objects(entry):
        if obj.get("class") == "DecalRoad":
            print(f"   file: {entry.filename[len(prefix):]}")
            print("  ", json.dumps(obj, indent=2)[:1400])
            found += 1
            break
    if found:
        break
if not found:
    print("   no DecalRoad found in this level")

# ---- 4. terrain material ----------------------------------------------------------------
print()
print("=" * 100)
print("4. TERRAIN MATERIAL AND TEXTURES")
print("=" * 100)
mat_entries = [e for e in z.infolist()
               if e.filename.lower().startswith(prefix.lower())
               and re.search(r"art/terrains?/main\.materials\.json$", e.filename, re.I)]
print(f"   material files: {[e.filename for e in mat_entries]}")

for entry in mat_entries[:1]:
    data = json.loads(z.read(entry).decode("utf-8", "replace"))
    sets = [v for v in data.values() if isinstance(v, dict) and v.get("class") == "TerrainMaterialTextureSet"]
    mats = [v for v in data.values() if isinstance(v, dict) and v.get("class") == "TerrainMaterial"]
    print(f"\n   texture sets ({len(sets)}):")
    for s in sets:
        print("     ", json.dumps(s))
    print(f"\n   materials ({len(mats)}); showing the first two:")
    for m in mats[:2]:
        print("     ", json.dumps(m, indent=6)[:1600])

# texture pixel sizes
tex_dir = prefix + "art/terrains/"
tex_entries = [e for e in z.infolist()
               if e.filename.lower().startswith(tex_dir.lower()) and e.filename.lower().endswith(".png")]
print(f"\n   textures beside the material: {len(tex_entries)}")
sizes = Counter()
for e in tex_entries[:40]:
    raw = z.read(e)[:33]
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", raw[16:24])
        sizes[(w, h)] += 1
print(f"   texture pixel sizes: {dict(sizes)}")

# ---- 5. TerrainBlock --------------------------------------------------------------------
print()
print("=" * 100)
print("5. HOW ITS TerrainBlock REFERENCES THE TEXTURE SET")
print("=" * 100)
for entry in items:
    for obj in read_objects(entry):
        if obj.get("class") == "TerrainBlock":
            print(f"   file: {entry.filename[len(prefix):]}")
            print("  ", json.dumps(obj, indent=2))
            break
    else:
        continue
    break

z.close()
