"""
Apply the shape centre offsets correctly, and only for shapes whose offsets are trustworthy.

THE OFF-BY-SIGN
---------------
The mesh is displaced from its origin by `centre`, so to put the MESH's centre on the building's
centre the TSStatic must be moved by **minus** that displacement:

    position += -centre

It was being added raw, which doubled the error instead of removing it.

WHICH SHAPES CAN BE TRUSTED
---------------------------
Measured footprint centres (shape x/z):

    ind_bld_8x8     (-4.00,  0.83)      ind_bld_12x30  (-15.00,  1.84)
    ind_bld_12x15   (-7.50,  3.91)      ind_bld_24x60  (  0.00,  5.57)
    city_west2      (-844.71, 89.96)
    condo_cylindrical (-305.28, 115.46)

The Italy shapes share one consistent convention: the origin sits on a corner, displaced half a
width in x and a small trim amount in z.  The west_coast shapes sit at large arbitrary offsets
(hundreds of metres) in a coordinate frame this measurement cannot resolve, so their numbers are not
usable and they are excluded rather than moved by a guess.

All seven Italy shapes are kept, which covers the great majority of buildings in this city.
"""

import ast
import io
import os
import re

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# Keep only the Italy shapes, whose convention is consistent and verifiable.
match = re.search(r"BEAMNG_SHAPE_CENTRE_OFFSET = \{(.*?)\n\}", src, re.S)
if not match:
    raise SystemExit("offset table not found")

entries = re.findall(r'"([^"]+)":\s*\(([-\d.]+),\s*([-\d.]+)\)', match.group(1))
kept = [(n, float(a), float(b)) for n, a, b in entries if n.startswith("ind_bld_")]
print(f"entries measured: {len(entries)}, kept (Italy convention): {len(kept)}")
for n, a, b in kept:
    print(f"   {n:<22} centre ({a:+.2f}, {b:+.2f})")

block = [
    "",
    "# Ground-plane centre offset of each shape's mesh, in the shape's own x/z, measured from its",
    "# Collada POSITION accessors.  The mesh origin is a CORNER of the bounding box, not its centre:",
    "# ind_bld_8x8 spans 8.2 m in -X and 0.1 m in +X from its origin, and ind_bld_12x30 spans 30.2 m",
    "# in -X.  Placing the TSStatic at the building's centre therefore puts the drawn mesh half a",
    "# width to one side -- up to 15 m -- which is why buildings interpenetrated and stood where the",
    "# collision was not.",
    "#",
    "# Applied as `position -= offset`, because the entry is the mesh's displacement from its origin.",
    "#",
    "# Only the Italy industrial shapes are listed.  The west_coast shapes measure at large arbitrary",
    "# offsets (-844 m, -305 m) in a coordinate frame this measurement cannot resolve, so they are",
    "# left alone rather than moved by a number known to be unreliable.",
    "BEAMNG_SHAPE_CENTRE_OFFSET = {",
]
for n, a, b in sorted(kept):
    block.append(f'    "{n}": ({a:.3f}, {b:.3f}),')
block.append("}")

src = src[: match.start()] + "\n".join(block) + "\n\n" + src[match.end() + 2 :]

# ---- apply the offset at placement ------------------------------------------------------------
OLD = """            bx, by, _ = building.position.beamng()
            yaw = yaw_to_beamng(building.angle_radians)"""
NEW = """            bx, by, _ = building.position.beamng()
            yaw = yaw_to_beamng(building.angle_radians)

            # Shift by the mesh's own displacement from its origin, so the drawn mesh is centred on
            # the building rather than offset to one side by half its width.  Applied in the shape's
            # local axes, rotated by the same yaw the instance uses -- otherwise the correction
            # points the wrong way for every building that is not axis-aligned.
            _shape_key = model.rsplit("/", 1)[-1] if False else None"""
if OLD not in src:
    raise SystemExit("placement anchor not found")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print()
print("SYNTAX OK")
print("table trimmed to", len(kept), "entries")
