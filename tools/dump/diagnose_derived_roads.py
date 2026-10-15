"""
Why do 1,695 derived roads paint only 3,426 cells?

Each road is 8 m wide over ~50 m, which at 4 m per cell should cover a few hundred cells each.  The
arithmetic says the stamps are landing almost nowhere, so the coordinates must be off.
"""

import json
import math
import sys

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
sys.path.insert(0, REPO + r"\tools")

import beamng_convert as B

layout, problems, warnings = B.load_city_layout(REPO + r"\exports\Cannes_city_layout.json")
print("layout problems:", problems)
print("buildings:", len(layout.buildings))

chains = B.derive_roads_from_buildings(layout.buildings)
print("derived chains:", len(chains))
print()

widths = [c["width"] for c in chains]
print("width: min %.2f  max %.2f" % (min(widths), max(widths)))

# Where are the chain endpoints in BeamNG space?
xs, ys, zs = [], [], []
lengths = []
for c in chains:
    pts = c["points"]
    (ax, ay, _), (bx, by, _) = pts[0].beamng(), pts[-1].beamng()
    xs += [ax, bx]
    ys += [ay, by]
    lengths.append(math.hypot(bx - ax, by - ay))

print("endpoint X range: %.1f .. %.1f" % (min(xs), max(xs)))
print("endpoint Y range: %.1f .. %.1f" % (min(ys), max(ys)))
print("segment length: min %.2f  median %.2f  max %.2f" % (
    min(lengths), sorted(lengths)[len(lengths) // 2], max(lengths)))

# What footprint does the terrain cover?
terrain = B.build_terrain(layout, [r for r in layout.roads if B.is_drivable(r)], verbose=False)
half = terrain.world_size * 0.5
print()
print("terrain: size %d  square %.2f m  world %.1f m" % (terrain.size, terrain.square_size, terrain.world_size))
print("terrain X: %.1f .. %.1f" % (terrain.position_x, terrain.position_x + terrain.world_size))
print("terrain Y: %.1f .. %.1f" % (terrain.position_y, terrain.position_y + terrain.world_size))

# How many endpoints fall inside?
inside = 0
for c in chains:
    for p in c["points"]:
        bx, by, _ = p.beamng()
        if (terrain.position_x <= bx <= terrain.position_x + terrain.world_size and
                terrain.position_y <= by <= terrain.position_y + terrain.world_size):
            inside += 1
total = sum(len(c["points"]) for c in chains)
print()
print("chain points inside the terrain footprint: %d / %d" % (inside, total))

# Compare with the CS1 roads, which paint fine.
road_pts = []
for r in layout.roads:
    if not B.is_drivable(r):
        continue
    for p in r.surface_polyline(max_sagitta=1.5):
        road_pts.append(p.beamng())
rxs = [p[0] for p in road_pts]
rys = [p[1] for p in road_pts]
print()
print("CS1 road point X range: %.1f .. %.1f" % (min(rxs), max(rxs)))
print("CS1 road point Y range: %.1f .. %.1f" % (min(rys), max(rys)))
