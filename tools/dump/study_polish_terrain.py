"""Study the terrain setup of polish_roads_v2: material file, texture set, textures, TerrainBlock."""

import json
import os
import re
import struct
import zipfile

ARCHIVE = os.path.join(
    os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo",
    "polish_roads_repo.zip",
)
LEVEL = "polish_roads_v2"
z = zipfile.ZipFile(ARCHIVE)
prefix = f"levels/{LEVEL}/"

print("=" * 100)
print("A. EVERY FILE UNDER art/terrains/ (and art/terrain/)")
print("=" * 100)
for e in z.infolist():
    low = e.filename.lower()
    if low.startswith(prefix.lower()) and re.search(r"art/terrains?/", low):
        print(f"   {e.file_size:>10,}  {e.filename[len(prefix):]}")

print()
print("=" * 100)
print("B. THE TERRAIN MATERIAL FILE, VERBATIM")
print("=" * 100)
mat_entries = [e for e in z.infolist()
               if e.filename.lower().startswith(prefix.lower())
               and re.search(r"art/terrains?/main\.materials\.json$", e.filename, re.I)]
for e in mat_entries:
    print(f"\n--- {e.filename[len(prefix):]}  ({e.file_size:,} bytes)")
    text = z.read(e).decode("utf-8", "replace")
    print(text[:3000])

print()
print("=" * 100)
print("C. TEXTURE PIXEL SIZES NEXT TO THE MATERIAL")
print("=" * 100)
for e in mat_entries:
    folder = os.path.dirname(e.filename) + "/"
    texes = [t for t in z.infolist() if t.filename.lower().startswith(folder.lower())]
    print(f"\n--- {folder}  ({len(texes)} files)")
    for t in texes[:20]:
        name = os.path.basename(t.filename)
        if name.lower().endswith(".png"):
            raw = z.read(t)[:33]
            if raw[:8] == b"\x89PNG\r\n\x1a\n":
                w, h = struct.unpack(">II", raw[16:24])
                print(f"     {name:<46} {w}x{h}   ({t.file_size:,} bytes)")
                continue
        if name.lower().endswith((".dds", ".link")):
            print(f"     {name:<46} {name.rsplit('.',1)[1].upper()}   ({t.file_size:,} bytes)")
        else:
            print(f"     {name:<46} ?      ({t.file_size:,} bytes)")

print()
print("=" * 100)
print("D. TerrainBlock AND THE .ter FILE")
print("=" * 100)
items = [e for e in z.infolist()
         if e.filename.lower().startswith(prefix.lower())
         and e.filename.lower().endswith("items.level.json")]
decoder = json.JSONDecoder()


def objs(entry):
    text = z.read(entry).decode("utf-8", "replace")
    out, i = [], 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        try:
            o, i = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        out.append(o)
    return out


for e in items:
    for o in objs(e):
        if o.get("class") == "TerrainBlock":
            print(f"   in {e.filename[len(prefix):]}")
            print(json.dumps(o, indent=6))
        if o.get("class") == "LevelInfo":
            print(f"\n   LevelInfo in {e.filename[len(prefix):]}")
            print(json.dumps(o, indent=6)[:900])

ters = [e for e in z.infolist()
        if e.filename.lower().startswith(prefix.lower()) and e.filename.lower().endswith(".ter")]
for t in ters:
    raw = z.read(t)
    ver = raw[0]
    grid = struct.unpack_from("<I", raw, 1)[0]
    n = grid * grid
    ns = 5 + n * 2 + n
    cnt = struct.unpack_from("<I", raw, ns)[0]
    off = ns + 4
    names = []
    for _ in range(cnt):
        end = raw.index(b"\x00", off)
        names.append(raw[off:end].decode("utf-8", "replace"))
        off = end + 1
    print(f"\n   .ter {t.filename[len(prefix):]}: version={ver} grid={grid} materials={names}")
    print(f"        file size {len(raw):,}  trailing {len(raw) - off}")

z.close()
