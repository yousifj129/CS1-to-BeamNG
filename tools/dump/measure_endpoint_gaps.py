"""
Measure how close emitted chain endpoints actually are, at several tolerances.

The first version bucketed on a 0.25 m grid and found nothing, which is only meaningful if the
endpoints are genuinely far apart.  This reports the nearest-neighbour distance between endpoints of
DIFFERENT chains, so the real gap is visible rather than hidden behind a grid choice.
"""

import json
import math
import os
import zipfile
from collections import Counter, defaultdict

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
z = zipfile.ZipFile(os.path.join(REPO, "dist", "cs1_cannes.zip"))
roads = [
    json.loads(l)
    for l in z.read("levels/Cannes/main/MissionGroup/Roads/items.level.json").decode().split("\n")
    if l.strip()
]
z.close()

ends = []
for index, road in enumerate(roads):
    ends.append((index, "start", road["nodes"][0]))
    ends.append((index, "end", road["nodes"][-1]))

print(f"roads {len(roads)}, endpoints {len(ends)}")
print()

# Nearest endpoint belonging to a DIFFERENT road.
nearest = []
for i, (ri, _wi, a) in enumerate(ends):
    best = None
    for j, (rj, _wj, b) in enumerate(ends):
        if ri == rj:
            continue
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        if best is None or d < best:
            best = d
    nearest.append(best)

nearest.sort()
print("nearest endpoint of a different road, per endpoint:")
print(f"   min    {nearest[0]:.4f} m")
print(f"   median {nearest[len(nearest)//2]:.4f} m")
print(f"   p90    {nearest[int(len(nearest)*0.9)]:.4f} m")
print(f"   max    {nearest[-1]:.4f} m")
print()

for tol in (0.01, 0.1, 0.5, 1.0, 2.0, 5.0):
    n = sum(1 for d in nearest if d <= tol)
    print(f"   endpoints within {tol:>5} m of another road's endpoint: {n:>5} / {len(nearest)}")

print()

# How many roads have an endpoint that comes within half its own width of another road at all?
close = 0
for index, road in enumerate(roads):
    half = road["nodes"][0][3] * 0.5
    for ri, _wi, a in ends:
        if ri == index:
            continue
        if math.hypot(road["nodes"][0][0] - a[0], road["nodes"][0][1] - a[1]) <= half:
            close += 1
            break
print(f"roads whose START is within its own half-width of another road endpoint: {close} / {len(roads)}")

print()
print("render properties:")
for key in ("startEndFade", "renderPriority", "distanceFade", "material", "overObjects"):
    c = Counter(str(r.get(key)) for r in roads)
    print(f"   {key:<16} {c.most_common(2)}")
