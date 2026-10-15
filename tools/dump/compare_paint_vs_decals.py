"""
The user's observation is the decisive clue: the painted road surface (the gravel/asphalt) outlines
every road correctly, but the road decal drawn on top of it is unreliable and has gaps.

Both are produced from the SAME source list, so if the painting is complete and the decals are not,
the loss is in the chaining step -- 1,244 source segments become 173 chains, and anything a chain
drops simply vanishes from the decals while the painting, which walks the raw roads, keeps it.

This measures the two against each other.
"""

import json
import math
import os
import sys
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
sys.path.insert(0, os.path.join(REPO, "tools"))
import beamng_convert as B

layout, _p, _w = B.load_city_layout(os.path.join(REPO, "exports", "Cannes_city_layout.json"))
roads = [r for r in layout.roads if B.is_drivable(r)]
chains = B.chain_roads(roads, 0.5)

print(f"source drivable segments : {len(roads)}")
print(f"chains emitted as decals : {len(chains)}")
print()

# How many source segments made it into a chain?
used = sum(c["segments"] for c in chains)
print(f"source segments consumed by chains : {used} / {len(roads)}")
print(f"source segments LOST in chaining   : {len(roads) - used}")
print()

# Chain length distribution -- short chains are the weakest decals.
lengths = []
for c in chains:
    pts = c["points"]
    total = sum(
        math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].z - pts[i].z)
        for i in range(len(pts) - 1)
    )
    lengths.append((total, len(pts)))

lengths.sort()
print("chain length (m):")
print(f"   min    {lengths[0][0]:.1f}   ({lengths[0][1]} nodes)")
print(f"   median {lengths[len(lengths)//2][0]:.1f}")
print(f"   max    {lengths[-1][0]:.1f}")
print()
print("chains under 20 m (a decal this short on a 16-22 m wide road is mostly fade):")
short = [l for l in lengths if l[0] < 20.0]
print(f"   {len(short)} / {len(lengths)}")
print()

# Compare with what per-segment emission would give.
seg_lengths = []
for r in roads:
    pts = r.surface_polyline(0.5)
    total = 0.0
    for i in range(len(pts) - 1):
        total += math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].z - pts[i].z)
    seg_lengths.append(total)

seg_lengths.sort()
print("If emitted ONE DecalRoad PER SOURCE SEGMENT instead:")
print(f"   decals      {len(roads)}")
print(f"   length min  {seg_lengths[0]:.1f}   median {seg_lengths[len(seg_lengths)//2]:.1f}   max {seg_lengths[-1]:.1f}")
print(f"   under 5 m   {sum(1 for s in seg_lengths if s < 5.0)}")
print()

# Widths: wide roads with short chains are the worst case for a visible gap.
print("widest roads and their chain length (a wide short decal shows a seam most):")
pairs = []
for c in chains:
    pts = c["points"]
    total = sum(
        math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].z - pts[i].z)
        for i in range(len(pts) - 1)
    )
    pairs.append((c["width"], total, c["segments"]))
pairs.sort(reverse=True)
for w, l, n in pairs[:8]:
    print(f"   width {w:>5.1f} m  chain length {l:>8.1f} m  from {n} segments")
