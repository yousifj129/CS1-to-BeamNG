"""
Do chains pass through the junctions they are cut at, or terminate there?

If a chain is cut at a junction, its endpoint should be AT that junction node.  If instead the
endpoint is tens of metres away, the graph walk is leaving the node before reaching it, which is
what the 224 m worst gap suggests.
"""

import json
import math
import os
import sys
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
sys.path.insert(0, os.path.join(REPO, "tools"))
import beamng_convert as B

layout, problems, _w = B.load_city_layout(os.path.join(REPO, "exports", "Cannes_city_layout.json"))
roads = [r for r in layout.roads if B.is_drivable(r)]
print(f"drivable CS1 roads: {len(roads)}")

# Node incidence, as chain_roads computes it.
incident = {}
for i, r in enumerate(roads):
    incident.setdefault(r.start_node_id, []).append((i, "start"))
    incident.setdefault(r.end_node_id, []).append((i, "end"))

junctions = {n for n, u in incident.items() if len(u) >= 3}
print(f"junction nodes (>=3 roads): {len(junctions)}")
print()

chains = B.chain_roads(roads, 0.5)
print(f"chains produced: {len(chains)}")
print()

# For each junction node, its CS1 position.
node_pos = {}
for r in roads:
    node_pos.setdefault(r.start_node_id, r.start_position.beamng())
    node_pos.setdefault(r.end_node_id, r.end_position.beamng())

# For every chain endpoint, how far is it from the nearest junction node?
dists = []
for c in chains:
    for point in (c["points"][0], c["points"][-1]):
        bx, by, _ = point.beamng()
        best = min(
            math.hypot(bx - node_pos[n][0], by - node_pos[n][1]) for n in junctions
        )
        dists.append(best)

dists.sort()
print("distance from each chain ENDPOINT to the nearest junction node:")
print(f"   min    {dists[0]:.2f} m")
print(f"   median {dists[len(dists)//2]:.2f} m")
print(f"   max    {dists[-1]:.2f} m")
print()
for tol in (1.0, 5.0, 20.0, 100.0):
    n = sum(1 for d in dists if d <= tol)
    print(f"   endpoints within {tol:>6} m of a junction: {n:>4} / {len(dists)}")

print()

# How many chain endpoints are at a junction at all, versus at a dead end?
at_junction = sum(1 for d in dists if d <= 1.0)
print(f"endpoints sitting exactly on a junction: {at_junction}")
print(f"endpoints elsewhere (dead ends / edges): {len(dists) - at_junction}")
print()

# Count how many junction nodes have no chain endpoint at all.
covered = set()
for c in chains:
    for point in (c["points"][0], c["points"][-1]):
        bx, by, _ = point.beamng()
        for n in junctions:
            if math.hypot(bx - node_pos[n][0], by - node_pos[n][1]) <= 1.0:
                covered.add(n)
print(f"junction nodes with at least one chain endpoint on them: {len(covered)} / {len(junctions)}")
print(f"junction nodes with NO chain endpoint                : {len(junctions) - len(covered)}")
print()
print(f"chains per junction on average: {len(dists) / max(1, len(junctions)):.2f} endpoints")
print("  (a junction needs at least 2 endpoints -- one per incoming chain -- to be joined)")
