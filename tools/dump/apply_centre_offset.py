"""
Apply the mesh centre offset at placement, rotated by the instance yaw.

The offset is stored in the shape's own local axes, so it must be rotated by the same yaw the
instance uses; adding it unrotated would point the correction the wrong way for every building that
is not axis-aligned, which is most of them.

    local offset (ox, oz) -> world (-ox*cos + oz*sin, -ox*sin - oz*cos) applied to position,
    with the sign inverted because the stored value is the mesh's displacement from its origin.

The correction is deliberately folded into the GROUND-PLANE position only; z is left to the terrain
sampling.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# Remove the broken fragment if it is present.
broken = """
            # Shift by the mesh's own displacement from its origin, so the drawn mesh is centred on
            # the building rather than offset to one side by half its width.  Applied in the shape's
            # local axes, rotated by the same yaw the instance uses -- otherwise the correction
            # points the wrong way for every building that is not axis-aligned.
            _shape_key = model.rsplit("/", 1)[-1] if False else None"""
if broken in src:
    src = src.replace(broken, "", 1)
    print("removed the broken fragment")

OLD = """            model, model_size, scale = choose_beamng_model(
                building.width, building.length, height
            )"""

NEW = """            model, model_size, scale = choose_beamng_model(
                building.width, building.length, height
            )

            # Centre the drawn mesh on the building.  Every shape's mesh origin is a corner of its
            # bounding box, so without this the building stands half a width to one side of where
            # the collision (and the road spacing) assumes it is.
            offset = BEAMNG_SHAPE_CENTRE_OFFSET.get(model.rsplit("/", 1)[-1])
            if offset:
                cos_o, sin_o = math.cos(yaw), math.sin(yaw)
                # Rotate the local offset into the instance's frame, then subtract it: the stored
                # value is the mesh's displacement FROM its origin, so the position must move by the
                # negative of it.
                dx_world = -offset[0] * cos_o + offset[1] * sin_o
                dy_world = -offset[0] * sin_o - offset[1] * cos_o
                bx += dx_world
                by += dy_world"""
if OLD not in src:
    raise SystemExit("model selection anchor not found")
src = src.replace(OLD, NEW, 1)

# Ground must be sampled at the final position: move the probe block after the offset.
OLD2 = """            # NOTE: the ground is sampled AFTER any road push (below), because a moved building
            # must take the elevation of where it ends up, not where it used to be.
            ground = self.ground_height(bx, by)
            if self.terrain is not None:"""
NEW2 = """            # NOTE: the ground is sampled here, after the centre offset above and before any road
            # push, and again after a push if one happens -- a building must take the elevation of
            # where it ends up, not where it used to be.
            ground = self.ground_height(bx, by)
            if self.terrain is not None:"""
if OLD2 in src:
    src = src.replace(OLD2, NEW2, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("offset applied:", "BEAMNG_SHAPE_CENTRE_OFFSET.get(model.rsplit" in src)
