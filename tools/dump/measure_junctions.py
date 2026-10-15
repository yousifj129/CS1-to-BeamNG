"""
Measure the road discontinuities, so the junction fix targets a real cause.

Three candidate explanations, tested in order:

  A. Roads sharing a node ID have endpoints at different coordinates, so chains break apart at the
     shared node even though they are logically connected.
  B. Roads that should connect have DIFFERENT node IDs (CS1 sometimes splits a node), so no
     connectivity is detected at all and the chains never join.
  C. Connectivity is fine and the gap is visual -- road widths or fade settings, not geometry.

The measurement decides which of these is true instead of assuming.
"""

import json
import math
from collections import Counter, defaultdict

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
data = json.load(open(REPO + r"\exports\Cannes_city_layout.json", encoding="utf-8"))
roads = data["roads"]

# node id -> list of (road index, which end, (x, y, z))
incident = defaultdict(list)
for i, r in enumerate(roads):
    s, e = r["startPosition"], r["endPosition"]
    incident[r["startNodeId"]].append((i, "start", (s["x"], s["y"], s["z"])))
    incident[r["endNodeId"]].append((i, "end", (e["x"], e["y"], e["z"])))

print(f"roads: {len(roads)}   distinct node ids: {len(incident)}")
print()

# ---- A. shared node, disagreeing coordinates -------------------------------------------------
shared = {n: v for n, v in incident.items() if len(v) > 1}
print(f"A. nodes used by more than one road: {len(shared)}")
worst = []
for node, uses in shared.items():
    pts = [u[2] for u in uses]
    mx = max(math.dist(p, q) for p in pts for q in pts)
    worst.append((mx, node, len(uses)))
worst.sort(reverse=True)

spread = [w[0] for w in worst]
if spread:
    over_1 = sum(1 for s in spread if s > 1.0)
    over_5 = sum(1 for s in spread if s > 5.0)
    print(f"   max endpoint disagreement at a shared node : {max(spread):.3f} m")
    print(f"   shared nodes disagreeing by more than 1 m  : {over_1}")
    print(f"   shared nodes disagreeing by more than 5 m  : {over_5}")
print("   worst 5:")
for mx, node, n in worst[:5]:
    print(f"      node {node:<8} {n} roads   spread {mx:.3f} m")

# ---- B. near-coincident endpoints with DIFFERENT node ids ------------------------------------
print()
# Bucket endpoints on a 0.5 m grid and see where different node ids meet.
buckets = defaultdict(set)
coords = {}
for node, uses in incident.items():
    for _i, _e, p in uses:
        key = (round(p[0] * 2), round(p[2] * 2))   # x, z are the ground plane
        buckets[key].add(node)
        coords.setdefault(node, p)

multi = {k: v for k, v in buckets.items() if len(v) > 1}
print(f"B. 0.5 m cells containing MORE THAN ONE node id: {len(multi)}")
extra = sum(len(v) - 1 for v in multi.values())
print(f"   => {extra} node ids are duplicates of a neighbour (split nodes, not connected)")

# ---- C. how far do the two ends of each road sit from their nearest other end -----------------
print()
# For each junction node, how many distinct roads attach?
degree = Counter(len(v) for v in incident.values())
print("C. node degree distribution (roads attached per node):")
for d in sorted(degree):
    print(f"      {d:>2} road(s) : {degree[d]:>5} nodes")
junctions = [n for n, v in incident.items() if len(v) >= 3]
print(f"   >= 3 roads (junctions) : {len(junctions)}")

# How many roads have at least one end at a junction?
at_junction = 0
for r in roads:
    if len(incident[r["startNodeId"]]) >= 3 or len(incident[r["endNodeId"]]) >= 3:
        at_junction += 1
print(f"   roads touching a junction at either end : {at_junction} / {len(roads)}")

# ---- D. width contrast at junctions -----------------------------------------------------------
print()
print("D. road widths (measured):")
w = [r["measuredWidth"] for r in roads]
w.sort()
print(f"   min {w[0]:.1f}  median {w[len(w)//2]:.1f}  max {w[-1]:.1f}")
print(f"   half of the roads are narrower than {w[len(w)//2]:.1f} m")
