"""Comprehensive check of the generated level."""

import json
import os
import struct
import xml.etree.ElementTree as ET

import numpy as np

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
MOD = os.path.join(REPO, "dist", "cs1_cannes")
LEVEL = os.path.join(MOD, "levels", "Cannes")
NS = "{http://www.collada.org/2005/11/COLLADASchema}"


def objs(path):
    decoder = json.JSONDecoder()
    text = open(path, encoding="utf-8").read()
    i = 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            return
        o, i = decoder.raw_decode(text, i)
        yield o


print("=" * 92)
print("1. .ter integrity")
print("=" * 92)
ter = os.path.join(LEVEL, "Cannes.ter")
blob = open(ter, "rb").read()
ver, grid = blob[0], struct.unpack_from("<I", blob, 1)[0]
n = grid * grid
ns = 5 + n * 2 + n
cnt = struct.unpack_from("<I", blob, ns)[0]
off = ns + 4
names = []
for _ in range(cnt):
    e = blob.index(b"\x00", off)
    names.append(blob[off:e].decode())
    off = e + 1
lay = np.frombuffer(blob, dtype=np.uint8, count=n, offset=5 + n * 2)
print(f"  version={ver}  grid={grid}  materials={names}  trailing={len(blob) - off}")
print(f"  layer values      : {np.unique(lay)[:6]}")
print(f"  file size         : {len(blob):,} bytes")

print()
print("=" * 92)
print("2. group declarations")
print("=" * 92)
for rel in ("main/items.level.json", "main/MissionGroup/items.level.json"):
    print(f"  --- {rel}")
    for o in objs(os.path.join(LEVEL, rel)):
        print(f"      {o['class']:<14} {o.get('name', '-'):<18} __parent={o.get('__parent', '-')}")

print()
print("=" * 92)
print("3. terrain material")
print("=" * 92)
mats = json.load(open(os.path.join(LEVEL, "art", "terrains", "main.materials.json"), encoding="utf-8"))
ts = [v for v in mats.values() if v.get("class") == "TerrainMaterialTextureSet"]
tm = [v for v in mats.values() if v.get("class") == "TerrainMaterial"]
print(f"  texture sets : {[t['name'] for t in ts]}")
for t in ts:
    print(f"     base={t['baseTexSize']} macro={t['macroTexSize']} detail={t['detailTexSize']}")
for m in tm:
    tex = {k: v for k, v in m.items() if isinstance(v, str) and k.endswith("Tex")}
    print(f"  material     : {m['internalName']}  groundmodel={m['groundmodelName']}  textures={len(tex)}")
    sizes = {k: v for k, v in m.items() if k.endswith("TexSize")}
    print(f"     sizes     : {sizes}")
tb = [o for o in objs(os.path.join(LEVEL, "main", "MissionGroup", "items.level.json"))
      if o["class"] == "TerrainBlock"][0]
print(f"  TerrainBlock.materialTextureSet = {tb.get('materialTextureSet')}")
print(f"  resolves against defined sets   = {tb.get('materialTextureSet') in [t['name'] for t in ts]}")

print()
print("=" * 92)
print("4. building shapes")
print("=" * 92)
shape_dir = os.path.join(MOD, "art", "shapes", "cs1_cannes")
for f in sorted(os.listdir(shape_dir)):
    if f.endswith(".dae"):
        root = ET.parse(os.path.join(shape_dir, f)).getroot()
        poly = root.find(".//" + NS + "polylist")
        bound = root.find(".//" + NS + "library_materials") is not None
        print(f"  {f:<28} valid XML  faces={poly.get('count'):<3} material-binding={bound}")
mm = json.load(open(os.path.join(shape_dir, "main.materials.json"), encoding="utf-8"))
print(f"  materials: {sorted(mm.keys())}")

print()
print("=" * 92)
print("5. building instances")
print("=" * 92)
base = os.path.join(LEVEL, "main", "MissionGroup", "Buildings")
shapes = {}
for f in sorted(os.listdir(base)):
    p = os.path.join(base, f, "items.level.json")
    if not os.path.isfile(p):
        continue
    for o in objs(p):
        if o["class"] == "TSStatic":
            key = (os.path.basename(o["shapeName"]), o["materialName"])
            shapes[key] = shapes.get(key, 0) + 1
print("  shape / material combinations in use:")
for (shape, mat), count in sorted(shapes.items(), key=lambda x: -x[1]):
    print(f"     {count:>5}x  {shape:<26} {mat}")
print(f"  total buildings: {sum(shapes.values())}")

print()
print("=" * 92)
print("6. preview + zip")
print("=" * 92)
prev = os.path.join(LEVEL, "_preview.png")
print(f"  _preview.png exists: {os.path.isfile(prev)}"
      + (f" ({os.path.getsize(prev):,} bytes)" if os.path.isfile(prev) else ""))
zp = os.path.join(REPO, "dist", "cs1_cannes.zip")
import zipfile
z = zipfile.ZipFile(zp)
roots = sorted({x.split("/")[0] for x in z.namelist() if x.strip("/")})
print(f"  zip roots: {roots}  integrity={'OK' if z.testzip() is None else 'CORRUPT'}")
z.close()
