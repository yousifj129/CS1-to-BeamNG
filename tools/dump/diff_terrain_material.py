"""
Diff my terrain material against the working map's, field by field.

`Missing Terrain texture: /` persists even though the set sizes and texture files match.  Rather
than reason about it again, this prints every key in polish_roads_v2's first material next to
mine, so a missing or differently-typed field is impossible to overlook.
"""

import io
import json
import os
import re
import sys
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
sys.path.insert(0, os.path.join(REPO, "tools"))

MINE = os.path.join(REPO, "dist", "cs1_cannes", "levels", "Cannes", "art", "terrains", "main.materials.json")
POLISH = os.path.join(
    os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo",
    "polish_roads_repo.zip",
)

mine = json.load(open(MINE, encoding="utf-8"))
my_mat = [v for v in mine.values() if v.get("class") == "TerrainMaterial"][0]
my_set = [v for v in mine.values() if v.get("class") == "TerrainMaterialTextureSet"][0]

with zipfile.ZipFile(POLISH) as z:
    ref = json.loads(
        z.read("levels/polish_roads_v2/art/terrains/main.materials.json").decode("utf-8", "replace")
    )
ref_mat = [v for v in ref.values() if v.get("class") == "TerrainMaterial"][0]
ref_set = [v for v in ref.values() if v.get("class") == "TerrainMaterialTextureSet"][0]

print("=" * 100)
print("TEXTURE SET")
print("=" * 100)
for key in sorted(set(my_set) | set(ref_set)):
    a, b = my_set.get(key, "<absent>"), ref_set.get(key, "<absent>")
    flag = "  " if a == b else "!!"
    print(f" {flag} {key:<18} mine={str(a):<28} ref={str(b)}")

print()
print("=" * 100)
print("MATERIAL  (texture fields shown as their kind: LOCAL / ENGINE)")
print("=" * 100)


def kind(v):
    if not isinstance(v, str):
        return v
    if "/levels/" in v:
        return "LOCAL:" + os.path.basename(v.replace("\\", "/"))
    if v.startswith("/assets/"):
        return "ENGINE:" + os.path.basename(v.replace("\\", "/"))
    return v


for key in sorted(set(my_mat) | set(ref_mat)):
    a, b = my_mat.get(key, "<absent>"), ref_mat.get(key, "<absent>")
    same = a == b
    if key.endswith("Tex"):
        same = kind(a) == kind(b)
        a, b = kind(a), kind(b)
    if key in ("internalName", "name", "persistentId"):
        same = True  # expected to differ
    flag = "  " if same else "!!"
    print(f" {flag} {key:<28} mine={str(a):<46} ref={str(b)}")

print()
print("=" * 100)
print("BASE TEXTURE PIXEL SIZES")
print("=" * 100)
import struct


def pixels(path):
    raw = open(path, "rb").read(33)
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return "not png"
    w, h = struct.unpack(">II", raw[16:24])
    return f"{w}x{h}"


tilt = os.path.join(REPO, "dist", "cs1_cannes", "levels", "Cannes", "art", "terrains")
for f in sorted(os.listdir(tilt)):
    if f.endswith(".png"):
        print(f"   {f:<34} {pixels(os.path.join(tilt, f))}")

with zipfile.ZipFile(POLISH) as z:
    print()
    for e in z.infolist():
        if e.filename.startswith("levels/polish_roads_v2/art/terrains/t_terrain_base") and e.filename.endswith(".png"):
            raw = z.read(e)[:33]
            w, h = struct.unpack(">II", raw[16:24])
            print(f"   REF {os.path.basename(e.filename):<30} {w}x{h}")
