import json
import os
import sys

ROOT = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
LEVEL = os.path.join(ROOT, "dist", "cs1_cannes", "levels", "Cannes")


def objects(path):
    text = open(path, encoding="utf-8").read()
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return
        obj, index = decoder.raw_decode(text, index)
        yield obj


print("=== level tree ===")
for folder, _dirs, files in os.walk(os.path.join(ROOT, "dist", "cs1_cannes")):
    for name in sorted(files):
        full = os.path.join(folder, name)
        rel = os.path.relpath(full, os.path.join(ROOT, "dist", "cs1_cannes"))
        print("  %10d  %s" % (os.path.getsize(full), rel))

print()
print("=== sky_and_sun/items.level.json ===")
for obj in objects(os.path.join(LEVEL, "main", "MissionGroup", "sky_and_sun", "items.level.json")):
    print("  %-12s name=%-14s position=%s" % (obj["class"], obj.get("name", ""), obj.get("position")))

print()
print("=== MissionGroup/items.level.json ===")
for obj in objects(os.path.join(LEVEL, "main", "MissionGroup", "items.level.json")):
    extra = ""
    if obj["class"] == "SpawnSphere":
        extra = " position=%s radius=%s dataBlock=%s sphereWeight=%s" % (
            obj.get("position"), obj.get("radius"), obj.get("dataBlock"), obj.get("sphereWeight"))
    if obj["class"] == "TerrainBlock":
        extra = " position=%s squareSize=%s maxHeight=%s" % (
            obj.get("position"), obj.get("squareSize"), obj.get("maxHeight"))
    print("  %-13s %-16s%s" % (obj["class"], obj.get("name", ""), extra))

print()
print("=== main/items.level.json (declares sub-groups) ===")
for obj in objects(os.path.join(LEVEL, "main", "items.level.json")):
    print("  %-10s name=%-14s __parent=%s" % (obj["class"], obj.get("name", ""), obj.get("__parent")))

print()
print("=== terrain material files ===")
for folder in ("terrains", "terrain"):
    path = os.path.join(LEVEL, "art", folder, "main.materials.json")
    if os.path.isfile(path):
        print("  %s -> %s" % (folder, open(path, encoding="utf-8").read().strip().replace("\n", " ")[:200]))

print()
print("=== spawn sanity: is it on the terrain and how flat is the ground? ===")
import struct
import numpy as np

ter_path = os.path.join(LEVEL, "Cannes.ter")
with open(ter_path, "rb") as handle:
    handle.read(1)
    size = struct.unpack("<I", handle.read(4))[0]
    heights = np.frombuffer(handle.read(size * size * 2), dtype="<u2").reshape(size, size).astype(np.float32)

block = None
for obj in objects(os.path.join(LEVEL, "main", "MissionGroup", "items.level.json")):
    if obj["class"] == "TerrainBlock":
        block = obj
spawn = None
for obj in objects(os.path.join(LEVEL, "main", "MissionGroup", "items.level.json")):
    if obj["class"] == "SpawnSphere":
        spawn = obj

px, py, pz = block["position"]
world = size * block["squareSize"]
scale = block["maxHeight"] / 65535.0


def height(x, y):
    gx = max(0.0, min(size - 1.001, (x - px) / world * (size - 1)))
    gy = max(0.0, min(size - 1.001, (y - py) / world * (size - 1)))
    x0, y0 = int(gx), int(gy)
    fx, fy = gx - x0, gy - y0
    top = heights[y0, x0] + (heights[y0, x0 + 1] - heights[y0, x0]) * fx
    bot = heights[y0 + 1, x0] + (heights[y0 + 1, x0 + 1] - heights[y0 + 1, x0]) * fx
    return pz + float(top + (bot - top) * fy) * scale


sx, sy, sz = spawn["position"]
print("  spawn position      :", spawn["position"])
print("  terrain there       : %.3f m" % height(sx, sy))
print("  spawn - terrain     : %.3f m  (should be ~+1.0)" % (sz - height(sx, sy)))
probes = [height(sx + dx, sy + dy) for dx, dy in
          ((-12, 0), (12, 0), (0, -12), (0, 12), (8, 8), (-8, -8), (-25, 0), (25, 0), (0, -25), (0, 25))]
print("  relief within 25 m  : %.3f m  (lower = flatter landing)" % (max(probes) - min(probes)))
print("  inside terrain      :", px <= sx <= px + world and py <= sy <= py + world)

print()
print("=== terrain height sampled at 6 road nodes vs the emitter's own value ===")
roads_path = os.path.join(LEVEL, "main", "MissionGroup", "Roads", "Roads_0", "items.level.json")
count = 0
for obj in objects(roads_path):
    for node in obj["nodes"][:1]:
        print("   node z=%.3f  terrain=%.3f  delta=%.4f" % (node[2], height(node[0], node[1]), node[2] - height(node[0], node[1])))
    count += 1
    if count >= 6:
        break
