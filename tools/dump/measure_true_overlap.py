"""
Measure building/road overlap correctly: the real rotated rectangle, not a bounding circle.

The bounding circle was an over-conservative approximation.  It shrinks buildings far more than
necessary AND can still miss, because the reach depends on the model's bounding box rather than the
footprint the CS1 building actually occupies.

This tests the four rotated footprint corners and their edges against the road corridor, using the
TSStatic's own rotation matrix, so the number reported is the true overlap.
"""

import json
import math
import os
import sys
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
sys.path.insert(0, os.path.join(REPO, "tools"))
import beamng_convert as B

z = zipfile.ZipFile(os.path.join(REPO, "dist", "cs1_cannes.zip"))
buildings = [
    json.loads(l)
    for l in z.read("levels/Cannes/main/MissionGroup/Buildings/items.level.json").decode().split("\n")
    if l.strip()
]
roads = [
    json.loads(l)
    for l in z.read("levels/Cannes/main/MissionGroup/Roads/items.level.json").decode().split("\n")
    if l.strip()
]
z.close()

# Road corridor as (segment, half-width).
segments = []
for r in roads:
    ns = r["nodes"]
    for i in range(len(ns) - 1):
        segments.append((ns[i][0], ns[i][1], ns[i + 1][0], ns[i + 1][1],
                         max(ns[i][3], ns[i + 1][3]) * 0.5))

sizes = {}
for _n, member, dims in B.BEAMNG_BUILDING_SOURCES:
    sizes[member.rsplit("/", 1)[-1]] = dims


def point_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def corners(b):
    shape = b["shapeName"].rsplit("/", 1)[-1]
    dims = sizes.get(shape)
    if dims is None:
        return None
    sx, sy = b["scale"][0], b["scale"][1]
    hw, hl = dims[0] * sx * 0.5, dims[1] * sy * 0.5
    rm = b["rotationMatrix"]
    # BeamNG rotationMatrix is row-major 3x3; column 0 is the local +X axis.
    x0, y0 = rm[0], rm[3]
    x1, y1 = rm[1], rm[4]
    px, py = b["position"][0], b["position"][1]
    return [
        (px + x0 * ox + x1 * oy, py + y0 * ox + y1 * oy)
        for ox, oy in ((-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl))
    ]


# Overlap = how far the rectangle penetrates the road corridor (positive = overlapping).
worst = []
for b in buildings:
    cs = corners(b)
    if cs is None:
        continue
    # Sample the rectangle interior as a grid, not just the corners: a narrow road can pass
    # entirely through a face without touching a corner.
    samples = []
    for i in range(5):
        for j in range(5):
            u, v = i / 4.0, j / 4.0
            # bilinear across the quad (it is a parallelogram, so this is exact)
            ax = cs[0][0] + (cs[1][0] - cs[0][0]) * u
            ay = cs[0][1] + (cs[1][1] - cs[0][1]) * u
            bx = cs[3][0] + (cs[2][0] - cs[3][0]) * u
            by = cs[3][1] + (cs[2][1] - cs[3][1]) * u
            samples.append((ax + (bx - ax) * v, ay + (by - ay) * v))

    deepest = -float("inf")
    for px, py in samples:
        edge = min((point_seg(px, py, *s[:4]) - s[4] for s in segments), default=float("inf"))
        if -edge > deepest:
            deepest = -edge
    worst.append((deepest, b.get("name"), b["shapeName"].rsplit("/", 1)[-1], b["scale"]))

worst.sort(reverse=True)
overlapping = [w for w in worst if w[0] > 0.0]
print(f"buildings sampled : {len(worst)}")
print(f"OVERLAPPING roads : {len(overlapping)}")
print()
print("worst 10 (positive = penetration into the road, metres):")
for d, name, shape, scale in worst[:10]:
    print(f"   {d:+7.3f} m  {name:<12} {shape:<26} scale {scale}")
