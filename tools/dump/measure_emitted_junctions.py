"""
Measure the emitted road junctions directly, in the built level.

Previous attempts reasoned about the source data.  This measures what is actually in the archive:
for every node shared by two or more chains, how far apart are the chain endpoints, and do the decal
widths actually overlap there?

If the endpoints coincide and the widths overlap, the geometry IS connected and the visible
discontinuity is a rendering property (fade, render priority, ordering).  If they do not coincide,
it is geometry.
"""

import json
import math
import os
import zipfile
from collections import defaultdict

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
z = zipfile.ZipFile(os.path.join(REPO, "dist", "cs1_cannes.zip"))
member = "levels/Cannes/main/MissionGroup/Roads/items.level.json"
roads = [json.loads(l) for l in z.read(member).decode().split("\n") if l.strip()]
z.close()

print(f"emitted DecalRoads: {len(roads)}")
print()

# Every road endpoint, bucketed on a 0.25 m grid to find coincident ends.
buckets = defaultdict(list)
for index, road in enumerate(roads):
    for which, node in (("start", road["nodes"][0]), ("end", road["nodes"][-1])):
        key = (round(node[0] * 4), round(node[1] * 4))
        buckets[key].append((index, which, node[3]))

shared = {k: v for k, v in buckets.items() if len(v) > 1}
print(f"endpoint locations (0.25 m grid) with more than one road: {len(shared)}")
sizes = defaultdict(int)
for v in shared.values():
    sizes[len(v)] += 1
for n in sorted(sizes):
    print(f"   {n} roads meet : {sizes[n]} locations")
print()

# Exact coincidence: how far apart are endpoints in the same bucket?
worst = 0.0
for key, uses in shared.items():
    pts = [(u[2], u[0], u[1]) for u in uses]
    for i in range(len(uses)):
        for j in range(i + 1, len(uses)):
            a = roads[uses[i][0]]["nodes"][0 if uses[i][1] == "start" else -1]
            b = roads[uses[j][0]]["nodes"][0 if uses[j][1] == "start" else -1]
            d = math.hypot(a[0] - b[0], a[1] - b[1])
            worst = max(worst, d)
print(f"greatest distance between endpoints sharing a location: {worst:.4f} m")
print()

# Do the widths overlap where roads meet?
print("width at shared locations (the decal half-width each side contributes):")
widths = []
for key, uses in list(shared.items())[:6]:
    ws = [u[2] for u in uses]
    widths.append((ws, sum(ws) / len(ws)))
for ws, avg in widths:
    print(f"   widths {ws}  mean {avg:.1f} m")

allw = [u[2] for uses in shared.values() for u in uses]
print()
print(f"   overall: {len(allw)} endpoints at shared locations, "
      f"width min {min(allw):.1f} median {sorted(allw)[len(allw)//2]:.1f} max {max(allw):.1f}")
print()

# Node counts and whether any road is a stub that cannot reach a junction.
counts = [len(r["nodes"]) for r in roads]
print(f"nodes per road: min {min(counts)} median {sorted(counts)[len(counts)//2]} max {max(counts)}")
print()

# Check the fade settings that could hide a join.
from collections import Counter

print("render properties that affect whether a join is visible:")
for key in ("startEndFade", "distanceFade", "renderPriority", "decalBias", "overObjects", "material"):
    c = Counter(str(r.get(key)) for r in roads)
    print(f"   {key:<16} {c.most_common(3)}")
