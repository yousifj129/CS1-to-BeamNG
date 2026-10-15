"""
Determine the correct sign and rotation for the mesh centre offset, empirically.

The offset is stored as the mesh's bounding-box centre in the shape's own local axes, e.g.
`ind_bld_8x8` is (-4.000, 0.833).  Applying it requires knowing both a sign and how it rotates, and
guessing produced 8 still-overlapping buildings where the previous raw-add produced none.

This tests both signs and both rotation directions against the real data and reports which leaves the
fewest overlaps -- a measurement rather than another guess.
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

z = zipfile.ZipFile(os.path.join(REPO, "dist", "cs1_cannes.zip"))
roads_emitted = [
    json.loads(l)
    for l in z.read("levels/Cannes/main/MissionGroup/Roads/items.level.json").decode().split("\n")
    if l.strip()
]
z.close()
segs = []
for r in roads_emitted:
    ns = r["nodes"]
    for i in range(len(ns) - 1):
        segs.append((ns[i][0], ns[i][1], ns[i + 1][0], ns[i + 1][1],
                     max(ns[i][3], ns[i + 1][3]) * 0.5))


def point_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


sizes = {m.rsplit("/", 1)[-1]: d for _n, m, d in B.BEAMNG_BUILDING_SOURCES}
offsets = B.BEAMNG_SHAPE_CENTRE_OFFSET

print(f"candidate transforms, scored by total penetration into roads across all buildings")
print()

variants = {
    "raw add (as first attempt)": lambda ox, oz, c, s: (ox, oz),
    "minus, rotate +yaw": lambda ox, oz, c, s: (-ox * c + oz * s, -ox * s - oz * c),
    "minus, rotate -yaw": lambda ox, oz, c, s: (-ox * c - oz * s, ox * s - oz * c),
    "add, rotate +yaw": lambda ox, oz, c, s: (ox * c - oz * s, ox * s + oz * c),
    "add, rotate -yaw": lambda ox, oz, c, s: (ox * c + oz * s, -ox * s + oz * c),
    "none (no offset)": lambda ox, oz, c, s: (0.0, 0.0),
}

for label, fn in variants.items():
    total_pen = 0.0
    overlapping = 0
    for b in layout.buildings:
        model, msize, scale = B.choose_beamng_model(b.width, b.length, max(b.height, 3.0))
        key = model.rsplit("/", 1)[-1]
        off = offsets.get(key)
        bx, by, _ = b.position.beamng()
        yaw = B.yaw_to_beamng(b.angle_radians)
        if off:
            dx, dy = fn(off[0], off[1], math.cos(yaw), math.sin(yaw))
            bx += dx
            by += dy

        hw = msize[0] * scale[0] * 0.5
        hl = msize[1] * scale[1] * 0.5
        c, s = math.cos(yaw), math.sin(yaw)
        deepest = -1e9
        for i in range(5):
            for j in range(5):
                ox = -hw + 2 * hw * i / 4.0
                oy = -hl + 2 * hl * j / 4.0
                px = bx + ox * c - oy * s
                py = by + ox * s + oy * c
                # Sign convention of rotationMatrix_z: x' = x cos - y sin, y' = x sin + y cos.
                edge = min((point_seg(px, py, *sg[:4]) - sg[4] for sg in segs), default=1e9)
                deepest = max(deepest, -edge)
        if deepest > 0:
            overlapping += 1
            total_pen += deepest

    print(f"   {label:<28} overlapping {overlapping:>4}   total penetration {total_pen:>10.1f} m")
