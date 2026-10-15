"""
Test junction connectivity correctly: endpoint against another chain's INTERIOR.

The previous measurement compared endpoint-to-endpoint distances and found a 10.6 m minimum, which
looked like disconnected roads.  That was the wrong metric: when a chain is cut at a junction, the
junction node becomes the END of the incoming chains but remains an INTERIOR node of any chain that
merely passes through.  A T-junction therefore has one chain's endpoint landing on another chain's
middle, and endpoint-to-endpoint distance says nothing about it.

This measures, for every chain endpoint, the distance to the nearest point on any other chain's
polyline.  That is the number that decides whether the network is geometrically joined.
"""

import json
import math
import os
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
z = zipfile.ZipFile(os.path.join(REPO, "dist", "cs1_cannes.zip"))
roads = [
    json.loads(l)
    for l in z.read("levels/Cannes/main/MissionGroup/Roads/items.level.json").decode().split("\n")
    if l.strip()
]
z.close()


def point_segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def distance_to_chain(px, py, road):
    nodes = road["nodes"]
    best = float("inf")
    for i in range(len(nodes) - 1):
        d = point_segment_distance(px, py, nodes[i][0], nodes[i][1], nodes[i + 1][0], nodes[i + 1][1])
        if d < best:
            best = d
    return best


ends = []
for index, road in enumerate(roads):
    ends.append((index, "start", road["nodes"][0], road["nodes"][0][3]))
    ends.append((index, "end", road["nodes"][-1], road["nodes"][-1][3]))

print(f"roads {len(roads)}, endpoints {len(ends)}")
print()

gaps = []
for ri, which, node, width in ends:
    best = float("inf")
    best_rj = None
    for rj, other in enumerate(roads):
        if rj == ri:
            continue
        d = distance_to_chain(node[0], node[1], other)
        if d < best:
            best = d
            best_rj = rj
    gaps.append((best, ri, which, width, best_rj))

gaps.sort()
print("distance from each chain endpoint to the nearest OTHER chain (its centre-line):")
print(f"   min    {gaps[0][0]:.4f} m")
print(f"   median {gaps[len(gaps)//2][0]:.4f} m")
print(f"   p90    {gaps[int(len(gaps)*0.9)][0]:.4f} m")
print(f"   max    {gaps[-1][0]:.4f} m")
print()

for tol in (0.1, 0.5, 1.0, 2.0, 5.0, 10.0):
    n = sum(1 for g in gaps if g[0] <= tol)
    print(f"   endpoints within {tol:>5} m of another chain: {n:>5} / {len(gaps)}")

print()

# The decisive test: does the endpoint land inside the other road's own half-width?
inside = 0
for gap, ri, which, width, rj in gaps:
    if rj is None:
        continue
    other_width = roads[rj]["nodes"][0][3]
    if gap <= min(width, other_width) * 0.5:
        inside += 1
print(f"endpoints landing within the other chain's HALF-WIDTH: {inside} / {len(gaps)}")
print()

print("worst 8 gaps (endpoint -> nearest other chain):")
for gap, ri, which, width, rj in gaps[-8:]:
    print(f"   road {ri:>3} {which:<5} width {width:>5.1f}  ->  road {rj:>3}  gap {gap:>8.2f} m")
