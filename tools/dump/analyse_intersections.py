"""
Three investigations, all data-driven.

1. Decode the "Missing Terrain texture" pattern.  Exactly 96 lines per session is suspiciously
   regular -- 8 terrain cells x 12?  The line before each error says which texture was consulted,
   so printing the surrounding log lines should name the missing resource rather than leave it
   as "/".

2. How polish_roads_v2 builds intersections.  Dump the properties of roads that touch a junction
   and compare them with roads that do not.

3. How it keeps buildings off roads -- whether it uses collision, spacing, or simply does not place
   TSStatics near roads.
"""

import collections
import json
import os
import re
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")
LOG = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "beamng.log")

print("=" * 100)
print("1. WHAT IS ACTUALLY MISSING -- context around the errors")
print("=" * 100)
lines = open(LOG, encoding="utf-8", errors="replace").read().split("\n")
hits = [i for i, l in enumerate(lines) if "Missing Terrain texture" in l]
print(f"   total 'Missing Terrain texture' lines: {len(hits)}")
if hits:
    # Print a window around the first occurrence, unfiltered, so the neighbouring lines show.
    first = hits[0]
    print(f"   first at line {first + 1}; showing 8 lines before and after:\n")
    for i in range(max(0, first - 8), min(len(lines), first + 9)):
        marker = ">>" if i in hits else "  "
        print(f"   {marker} {lines[i].strip()[:150]}")

# Which distinct textures does the level's material reference?
print()
print("=" * 100)
print("2. polish_roads_v2 INTERSECTIONS")
print("=" * 100)

z = zipfile.ZipFile(os.path.join(REPO_MODS, "polish_roads_repo.zip"))
PREFIX = "levels/polish_roads_v2/"

roads = []
for e in z.infolist():
    low = e.filename.lower()
    if not low.startswith(PREFIX) or not low.endswith("items.level.json"):
        continue
    if e.file_size > 4_000_000:
        continue
    try:
        text = z.read(e).decode("utf-8", "replace")
    except Exception:
        continue
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("class") == "DecalRoad":
            roads.append(obj)

print(f"   DecalRoads total: {len(roads)}")

# Which optional properties do they set, and how often?
props = collections.Counter()
for r in roads:
    for k in r:
        props[k] += 1
print("\n   property frequency:")
for k, c in props.most_common():
    print(f"      {k:<22} {c:>6}  ({100 * c / len(roads):.0f}%)")

print("\n   property VALUE samples for the interesting ones:")
for key in ("material", "autoJunction", "autoLanes", "oneWay", "gatedRoad", "drivability",
            "detail", "smoothness", "breakAngle", "improvedSpline", "startEndFade",
            "textureLength", "renderPriority", "decalBias", "distanceFade", "speedLimit"):
    values = collections.Counter(
        json.dumps(r[key]) for r in roads if key in r
    )
    if values:
        top = ", ".join(f"{v} x{c}" for v, c in values.most_common(5))
        print(f"      {key:<18} {top}")

# Node counts and widths
node_counts = [len(r.get("nodes") or []) for r in roads]
print(f"\n   nodes per road: min={min(node_counts)} median={sorted(node_counts)[len(node_counts)//2]} max={max(node_counts)}")
widths = [r["nodes"][0][3] for r in roads if r.get("nodes") and len(r["nodes"][0]) > 3]
if widths:
    print(f"   widths: min={min(widths):.1f} median={sorted(widths)[len(widths)//2]:.1f} max={max(widths):.1f}")

# Do their chains END at a junction or run through it?
print()
print("=" * 100)
print("3. HOW polish_roads_v2 PLACES BUILDINGS AND PROPS vs ROADS")
print("=" * 100)
z.close()

# Count TSStatic vs DecalRoad and see whether any TSStatic sits within a road's width
z = zipfile.ZipFile(os.path.join(REPO_MODS, "polish_roads_repo.zip"))
statics = []
for e in z.infolist():
    low = e.filename.lower()
    if not low.startswith(PREFIX) or not low.endswith("items.level.json") or e.file_size > 4_000_000:
        continue
    try:
        text = z.read(e).decode("utf-8", "replace")
    except Exception:
        continue
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("class") == "TSStatic":
            statics.append(obj)
print(f"   TSStatics: {len(statics)}  (ours: 1463)")
if statics:
    keys = collections.Counter(k for s in statics for k in s)
    print("   property frequency (top 12):")
    for k, c in keys.most_common(12):
        print(f"      {k:<22} {c:>6}")
z.close()
