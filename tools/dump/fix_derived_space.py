"""
Fix a coordinate-space mix-up in the building-derived roads.

`Vec3` stores **CS1** coordinates and `Vec3.beamng()` converts them.  The generator called
`.beamng()` on each building *and* stored the result in a `Vec3`, so the conversion was applied
twice:

    CS1 (-229.34, 221.53, 451.27)
      .beamng() -> (229.34, 451.27, 221.53)     correct BeamNG tuple
      stored in Vec3 as x=229.34, y=451.27, z=221.53
      .beamng() again -> (-229.34, 221.53, 451.27)

The second conversion treats 451.27 as CS1 **height** and the north ordinate as CS1 z, which is not
what those numbers are.  Every derived road therefore landed on y = 0 and the whole network
collapsed onto a single line -- visible as 1,695 roads painting only 3,426 terrain cells.

The generator now works in CS1 space throughout and lets the pipeline convert once, at emit time.
The ground-plane ordinate that matters is CS1 **z** (north); CS1 y is elevation, which the terrain
provides when the road is emitted.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = """    centres = []
    for b in buildings:
        # BeamNG ground plane is (x, y): x is east/west, y is north/south (from CS1's z).  Both are
        # kept -- an earlier version dropped `by` and every road collapsed onto the line y = 0.
        bx, by, _ = b.position.beamng()
        centres.append((bx, by, b))"""
NEW = """    # Work in CS1 space.  `Vec3` holds CS1 coordinates and `beamng()` performs the conversion, so
    # converting here would convert twice and collapse the network.  The ground plane is CS1 (x, z):
    # x is east/west and z is north/south; CS1 y is elevation, which the terrain supplies later.
    centres = []
    for b in buildings:
        centres.append((b.position.x, b.position.z, b))"""
if OLD not in src:
    raise SystemExit("centres anchor not found")
src = src.replace(OLD, NEW, 1)

OLD2 = """        # Vec3(x, y, z) with BeamNG mapping x->east, y->north, z->up.  The bow offset is applied to
        # the ground-plane ordinate (`by`), not to a copy of it.
        start = Vec3(ax, ay, 0.0)
        control = Vec3(mx, my, 0.0)
        end = Vec3(bx, by, 0.0)"""
NEW2 = """        # CS1-space Vec3s: x = east/west, z = north/south ground plane, y = elevation (left at 0
        # and replaced by the terrain surface when the road is emitted).
        start = Vec3(ax, 0.0, ay)
        control = Vec3(mx, 0.0, my)
        end = Vec3(bx, 0.0, by)"""
if OLD2 not in src:
    raise SystemExit("control point anchor not found")
src = src.replace(OLD2, NEW2, 1)

OLD3 = """            px = u * u * start.x + 2 * u * t * control.x + t * t * end.x
            py = u * u * start.y + 2 * u * t * control.y + t * t * end.y
            # px is the east ordinate, py the north ordinate; z (up) is filled in from the terrain
            # when the road is emitted.
            points.append(Vec3(px, py, 0.0))"""
NEW3 = """            px = u * u * start.x + 2 * u * t * control.x + t * t * end.x
            pz = u * u * start.z + 2 * u * t * control.z + t * t * end.z
            points.append(Vec3(px, 0.0, pz))"""
if OLD3 not in src:
    raise SystemExit("flatten anchor not found")
src = src.replace(OLD3, NEW3, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("centres use CS1 x/z :", "centres.append((b.position.x, b.position.z, b))" in src)
print("points in CS1 space :", "points.append(Vec3(px, 0.0, pz))" in src)
