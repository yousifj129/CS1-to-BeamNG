"""
Measure the true visual extents of each building shape and compare with the size table.

The shapes have NO `collision-` meshes -- every geometry is a visual mesh, and none carries a node
translation.  So `collisionType: "Collision Mesh"` has nothing to bind and the engine falls back to
a bounding box, which is why collisions do not match what is seen.

The shapes are also multi-mesh: `ind_bld_12x30` has five separate meshes.  If one of them (trim,
cabling, a rooftop unit) extends well past the main mass, the bounding box -- and therefore the
collision -- is much larger than the building looks.

This reads every mesh's POSITION accessor min/max, which is the authoritative bound.
"""

import os
import re
import zipfile

GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"

SHAPES = [
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_8x8.dae", (8.20, 8.20, 5.73)),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x15.dae", (15.20, 12.20, 12.55)),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x30.dae", (30.10, 12.11, 10.92)),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_24x60.dae", (60.27, 31.07, 17.14)),
    ("west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/condo_cylindrical.dae", (56.19, 56.63, 87.24)),
]


def nums(text):
    return [float(v) for v in text.split()]


for archive, member, claimed in SHAPES:
    path = os.path.join(GAME, "content", "levels", archive)
    with zipfile.ZipFile(path) as z:
        text = z.read(member).decode("utf-8", "replace")

    name = os.path.basename(member)
    print("=" * 88)
    print(f"{name}   size table says {claimed}")
    print("=" * 88)

    geoms = re.findall(r"<geometry[^>]*id=\"([^\"]+)\"[^>]*>(.*?)</geometry>", text, re.S)
    overall = None
    for gid, body in geoms:
        # Only the POSITION source of this geometry.
        pos = re.search(r'<source[^>]*id="[^"]*positions?[^"]*"[^>]*>(.*?)</source>', body, re.S)
        if not pos:
            pos = re.search(r"<source[^>]*>(.*?)</source>", body, re.S)
        if not pos:
            continue
        arr = re.search(r'<float_array[^>]*>(.*?)</float_array>', pos.group(1), re.S)
        if not arr:
            continue
        values = nums(arr.group(1))
        if len(values) < 3:
            continue
        xs, ys, zs = values[0::3], values[1::3], values[2::3]
        lo = (min(xs), min(ys), min(zs))
        hi = (max(xs), max(ys), max(zs))
        size = tuple(hi[i] - lo[i] for i in range(3))
        print(f"   {gid:<34} size {tuple(round(v,2) for v in size)}"
              f"  min {tuple(round(v,2) for v in lo)}")
        if overall is None:
            overall = [list(lo), list(hi)]
        else:
            for i in range(3):
                overall[0][i] = min(overall[0][i], lo[i])
                overall[1][i] = max(overall[1][i], hi[i])

    if overall:
        size = tuple(round(overall[1][i] - overall[0][i], 2) for i in range(3))
        print(f"   {'OVERALL BOUNDING BOX':<34} size {size}")
        # BeamNG uses X, Z as the ground plane and Y up in DAE convention; compare generously.
        dims = sorted(size[:2] if size[2] > size[0] else [size[0], size[2]])
        print(f"   size table (x, y) = {claimed[0]}, {claimed[1]}")
        print(f"   largest two extents = {dims[0]:.2f}, {dims[1]:.2f}")
        if dims[1] > max(claimed[0], claimed[1]) * 1.15:
            print("   ** BOUNDING BOX EXCEEDS THE SIZE TABLE BY >15% **")
    print()
