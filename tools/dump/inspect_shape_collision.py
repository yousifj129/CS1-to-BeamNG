"""
Compare each building shape's collision geometry against its visual bounds.

Measured already: by the true rotated rectangle, **zero** of 1,463 buildings overlap a road.  So if
cars still collide where they should not, the collision geometry is not the same size as the visual
geometry -- or it has a different origin.

This reads the Collada files and compares the extents of the `collision-` meshes against the visual
ones, and reports any node translations that would offset the collision relative to the visuals.
"""

import os
import re
import zipfile

GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"

SHAPES = [
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_8x8.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x15.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x30.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_24x60.dae"),
    ("west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/condo_cylindrical.dae"),
]


def floats(text):
    return [float(v) for v in text.split()]


for archive, member in SHAPES:
    path = os.path.join(GAME, "content", "levels", archive)
    if not os.path.isfile(path):
        print("missing", archive)
        continue
    with zipfile.ZipFile(path) as z:
        try:
            text = z.read(member).decode("utf-8", "replace")
        except KeyError:
            print("missing member", member)
            continue

    name = os.path.basename(member)
    # Geometry ids and their vertex position sources.
    geoms = re.findall(r'<geometry[^>]*id="([^"]+)"[^>]*>(.*?)</geometry>', text, re.S)
    # Node id -> geometry instance, and any translation on the node.
    nodes = re.findall(r'<node[^>]*>(.*?)</node>', text, re.S)

    print("=" * 92)
    print(name)
    print("=" * 92)
    print(f"  geometries: {len(geoms)}")
    for gid, body in geoms:
        kind = "COLLISION" if "collision" in gid.lower() else "visual   "
        # Count vertices and read the accessor min/max if present.
        mins = re.findall(r'<accessor[^>]*min="([^"]*)"[^>]*max="([^"]*)"', body)
        count = re.search(r'<float_array[^>]*count="(\d+)"', body)
        n = int(count.group(1)) // 3 if count else 0
        print(f"    {kind} {gid:<44} verts~{n}")
        for mn, mx in mins[:1]:
            try:
                a, b = floats(mn), floats(mx)
                print(f"                 min {[round(v,2) for v in a[:3]]}  max {[round(v,2) for v in b[:3]]}")
            except Exception:
                pass

    # Node translations, which offset a mesh relative to the shape origin.
    trans = re.findall(r'<translate[^>]*sid="([^"]*)"[^>]*>([^<]*)</translate>', text)
    if trans:
        print("  node translations:")
        for sid, val in trans[:8]:
            print(f"    {sid:<24} {val.strip()}")
    else:
        print("  node translations: none")

    # Which materials the collision mesh binds.
    binds = re.findall(r'<instance_material[^>]*symbol="([^"]+)"', text)
    coll_binds = [b for b in binds if "collision" in b.lower()]
    print(f"  instance_material symbols: {len(binds)}, collision-related: {coll_binds}")
