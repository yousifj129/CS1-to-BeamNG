"""
Verify that no building footprint overlaps a road surface.

Reports the closest approach of any building's scaled footprint to a road edge, so the clearance
setting is confirmed by measurement rather than assumed.
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
segments = B.road_segments(roads)
print(f"roads {len(roads)}, flattened segments {len(segments)}")

z = zipfile.ZipFile(os.path.join(REPO, "dist", "cs1_cannes.zip"))
buildings = [
    json.loads(l)
    for l in z.read("levels/Cannes/main/MissionGroup/Buildings/items.level.json").decode().split("\n")
    if l.strip()
]
z.close()
print(f"emitted buildings {len(buildings)}")
print()

# Each building: check its four scaled, rotated footprint corners against the road edges.
worst = []
overlapping = 0
for b in buildings:
    shape = b["shapeName"].rsplit("/", 1)[-1]
    size = None
    for member, dims in B.BEAMNG_BUILDING_MODELS:
        if member.endswith(shape):
            size = dims
            break
    if size is None:
        continue

    sx, sy, _sz = b["scale"]
    half_w = size[0] * sx * 0.5
    half_l = size[1] * sy * 0.5

    # rotationMatrix column 0 gives the facing direction in the ground plane.
    rm = b["rotationMatrix"]
    yaw = math.atan2(rm[3], rm[0])
    cos_a, sin_a = math.cos(yaw), math.sin(yaw)

    bx, by = b["position"][0], b["position"][1]
    best = float("inf")
    # Bounding circle, not rotated corners: a corner test under-reports when the model axes
    # differ from the TSStatic rotation, which is what let an overlapping building pass.
    reach = math.hypot(half_w, half_l)
    best = B.road_clearance(bx, by, segments) - reach

    worst.append((best, b.get("name"), shape, b["scale"]))
    if best < 0:
        overlapping += 1

worst.sort()
print("closest approach of any footprint corner to a road edge:")
print(f"   min    {worst[0][0]:+.3f} m   ({worst[0][1]})")
print(f"   median {worst[len(worst)//2][0]:+.3f} m")
print()
print(f"buildings whose footprint overlaps a road (negative clearance): {overlapping} / {worst.__len__()}")
print()
print("tightest 6:")
for d, name, shape, scale in worst[:6]:
    print(f"   {d:+.3f} m  {name:<12} {shape:<28} scale {scale}")
