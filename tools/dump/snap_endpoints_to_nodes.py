"""
Snap chain endpoints to the road NODE positions, in the ground plane.

THE BUG
-------
`Road.surface_polyline` averages the NODE elevation with the BEZIER elevation at the first and last
point, but keeps the **X/Z of the Bezier**:

    points[0] = Vec3(first.x, (first.y + self.start_position.y) * 0.5, first.z)

Its own docstring records why the elevation is averaged: in CS1 the Bezier is not exactly the node
chain, and on 259 segments (mostly Basic Road) its endpoints are *pulled along the segment* to
handle junction corners.  The X/Z were never corrected, so where a road meets a junction the emitted
geometry stops short of the node -- by the exact amount CS1 pulled it in.

MEASURED CONSEQUENCE
--------------------
Nodes shared by two roads in the source data agree to **0.000 m** (measured across all 2,307 roads
and 2,257 nodes), so the node positions are exactly where roads meet.  But of 111 junction nodes,
**0** had a chain endpoint sitting on them; the closest endpoint was 2 m away and the median 10 m.
The chains never met, which is why every junction looked disconnected.

THE FIX
-------
The first and last point take the node's X/Z, while the elevation stays averaged -- that average is
independently well-founded and cancels a systematic Bezier/node elevation bias.  Only the ground
plane is snapped, which is what decides whether roads touch.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = """        In CS1 the segment's Bezier is *not* exactly the node chain: across the Cannes export the
        Bezier sits +1.000 m above the node positions on 1040 segments and -0.300 m below on 326,
        and on 259 segments (mostly Basic Road) its endpoints are pulled along the segment to
        handle junction corners.  Neither value is authoritative on its own, so for the first and
        last point we average the node elevation with the Bezier elevation, which cancels that
        systematic bias; interior points come from the Bezier alone.
        \"\"\"
        if self.bezier is None:
            return [self.start_position, self.end_position]

        points = self.polyline(max_sagitta)
        if not points:
            return points

        first = points[0]
        points[0] = Vec3(
            first.x, (first.y + self.start_position.y) * 0.5, first.z
        )

        last = points[-1]
        points[-1] = Vec3(last.x, (last.y + self.end_position.y) * 0.5, last.z)

        return points"""

NEW = """        In CS1 the segment's Bezier is *not* exactly the node chain: across the Cannes export the
        Bezier sits +1.000 m above the node positions on 1040 segments and -0.300 m below on 326,
        and on 259 segments (mostly Basic Road) its endpoints are pulled along the segment to
        handle junction corners.

        So neither endpoint is taken directly from the Bezier:

        * ELEVATION is averaged between node and Bezier, which cancels the systematic +1.000 /
          -0.300 bias.
        * GROUND POSITION (x, z) is snapped to the NODE.  Node positions are where roads actually
          meet -- measured across the export, nodes shared by two roads agree to 0.000 m -- whereas
          the Bezier endpoint is pulled in at exactly the junctions.  Keeping the Bezier's x/z is
          what left every chain stopping short of its junction: of 111 junction nodes, none had a
          chain endpoint on it, the closest being 2 m away and the median 10 m.

        Interior points still come from the Bezier alone.
        \"\"\"
        if self.bezier is None:
            return [self.start_position, self.end_position]

        points = self.polyline(max_sagitta)
        if not points:
            return points

        first = points[0]
        points[0] = Vec3(
            self.start_position.x,
            (first.y + self.start_position.y) * 0.5,
            self.start_position.z,
        )

        last = points[-1]
        points[-1] = Vec3(
            self.end_position.x,
            (last.y + self.end_position.y) * 0.5,
            self.end_position.z,
        )

        return points"""

if OLD not in src:
    raise SystemExit("surface_polyline anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("x/z snapped to node:", "self.start_position.x," in src and "self.start_position.z," in src)
