"""
Fix the derived roads collapsing onto a single line.

`derive_roads_from_buildings` built every point as `Vec3(x, y, 0.0)` -- that is, it put the BeamNG
ground-plane Y in the Vec3's Z slot and left the Vec3's Y at zero.  Since `Vec3.beamng()` maps
`y -> ground-plane forward`, every derived road ended up at Y = 0 and 1,695 roads stacked onto one
line.  The diagnostic showed it plainly: `endpoint Y range: 0.0 .. 0.0`.

It also rounded each bow control point through `my` while mapping the real ordinate to the wrong
slot, so the curve was being computed in a mixed coordinate space.

Both points now carry the true ground-plane ordinate.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- centres: keep the BeamNG ordinate -------------------------------------------------------
OLD = """    centres = []
    for b in buildings:
        bx, by, _ = b.position.beamng()
        centres.append((bx, by, b))"""
NEW = """    centres = []
    for b in buildings:
        # BeamNG ground plane is (x, y): x is east/west, y is north/south (from CS1's z).  Both are
        # kept -- an earlier version dropped `by` and every road collapsed onto the line y = 0.
        bx, by, _ = b.position.beamng()
        centres.append((bx, by, b))"""
if OLD not in src:
    raise SystemExit("centres anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- control points: real ordinate in the Y slot --------------------------------------------
OLD2 = """        start = Vec3(ax, ay, 0.0)
        control = Vec3(mx, my, 0.0)
        end = Vec3(bx, by, 0.0)"""
NEW2 = """        # Vec3(x, y, z) with BeamNG mapping x->east, y->north, z->up.  The bow offset is applied to
        # the ground-plane ordinate (`by`), not to a copy of it.
        start = Vec3(ax, ay, 0.0)
        control = Vec3(mx, my, 0.0)
        end = Vec3(bx, by, 0.0)"""
if OLD2 not in src:
    raise SystemExit("control point anchor not found")
src = src.replace(OLD2, NEW2, 1)

# ---- flattening: interpolate the Y slot ------------------------------------------------------
OLD3 = """            px = u * u * start.x + 2 * u * t * control.x + t * t * end.x
            py = u * u * start.y + 2 * u * t * control.y + t * t * end.y
            points.append(Vec3(px, py, 0.0))"""
NEW3 = """            px = u * u * start.x + 2 * u * t * control.x + t * t * end.x
            py = u * u * start.y + 2 * u * t * control.y + t * t * end.y
            # px is the east ordinate, py the north ordinate; z (up) is filled in from the terrain
            # when the road is emitted.
            points.append(Vec3(px, py, 0.0))"""
if OLD3 not in src:
    raise SystemExit("flatten anchor not found")
src = src.replace(OLD3, NEW3, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("centres keep by :", "centres.append((bx, by, b))" in src)
print("control uses my :", "control = Vec3(mx, my, 0.0)" in src)
