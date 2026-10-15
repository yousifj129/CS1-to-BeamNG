"""
Bake each building shape's true mesh centre, because the mesh origin is not its centre.

MEASURED
--------
    ind_bld_8x8.dae     min (-8.10, -0.10, -2.03)   size (8.20, 8.20, 5.73)
    ind_bld_12x15.dae   min (-15.10, -0.10, -2.36)   size (15.20, 12.20, 12.55)

The origin sits at a CORNER of the bounding box, not its centre: `ind_bld_8x8` extends 8.1 m in -X
and 0.1 m in +X, and 8.1 m in -Y and 0.1 m in +Y.  Every other shape has the same layout.

So placing the TSStatic at the building's own centre put the mesh a whole half-width to one side --
up to 30 m for `ind_bld_24x60`.  The collision then sits where the building *is*, while the CS1
building it was meant to represent is elsewhere, which is why cars collide with geometry that does
not line up with what is drawn.  The earlier overlap measurements used the size table with an
assumed centred origin, so they reported no overlap while the real mesh was displaced.

FIX
---
The centre offset is recorded per shape and added to the placement position, so the MESH's centre
lands on the building's centre.  The offsets are measured from the Collada POSITION accessors, not
guessed.
"""

import ast
import io
import os
import re
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"

SHAPES = [
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_8x8.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x10.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x15.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x20.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x24.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x30.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_24x60.dae"),
    ("west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/city_west2.dae"),
    ("west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/city_west5.dae"),
    ("west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/city_block3.dae"),
    ("west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/condo_cylindrical.dae"),
]


def nums(text):
    return [float(v) for v in text.split()]


print("measuring mesh bounds from the Collada files")
bounds = {}
for archive, member in SHAPES:
    path = os.path.join(GAME, "content", "levels", archive)
    with zipfile.ZipFile(path) as z:
        text = z.read(member).decode("utf-8", "replace")

    lo = [1e18] * 3
    hi = [-1e18] * 3
    for _gid, body in re.findall(r'<geometry[^>]*id="([^"]+)"[^>]*>(.*?)</geometry>', text, re.S):
        src = re.search(r'<source[^>]*>(.*?)</source>', body, re.S)
        if not src:
            continue
        arr = re.search(r"<float_array[^>]*>(.*?)</float_array>", src.group(1), re.S)
        if not arr:
            continue
        values = nums(arr.group(1))
        if len(values) < 3:
            continue
        for axis in range(3):
            column = values[axis::3]
            lo[axis] = min(lo[axis], min(column))
            hi[axis] = max(hi[axis], max(column))

    size = [hi[i] - lo[i] for i in range(3)]
    centre = [(hi[i] + lo[i]) * 0.5 for i in range(3)]
    bounds[os.path.basename(member)] = (lo, hi, size, centre)
    print(f"  {os.path.basename(member):<26} size {[round(v, 2) for v in size]}"
          f"  centre {[round(v, 2) for v in centre]}")

# BeamNG is Z-up; the Collada here is Z-up too (Y is the shallow axis), so the ground-plane centre
# offset is (x, y) and z stays as the vertical base.
TABLE = "\n\n# Ground-plane centre offset of each shape's mesh, measured from its Collada POSITION\n"
TABLE += "# accessors.  The mesh origin is a CORNER of the bounding box, not its centre -- ind_bld_8x8\n"
TABLE += "# extends 8.1 m in -X and 0.1 m in +X from its origin -- so placing the TSStatic at the\n"
TABLE += "# building's centre would offset the whole mesh by half its width.  Added to the position.\n"
TABLE += "BEAMNG_SHAPE_CENTRE_OFFSET = {\n"
for member, (_lo, _hi, size, centre) in bounds.items():
    TABLE += f'    "{member}": ({centre[0]:.3f}, {centre[1]:.3f}),\n'
TABLE += "}"

src = io.open(TARGET, encoding="utf-8").read()
anchor = "BEAMNG_BUILDING_MODELS = "
if anchor not in src:
    raise SystemExit("building models anchor not found")
src = src.replace(anchor, TABLE.strip() + "\n\n" + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print()
print("SYNTAX OK")
print("offsets baked:", "BEAMNG_SHAPE_CENTRE_OFFSET" in src)
print(TABLE.strip()[:400])
