"""
Simplify the clearance rule, and make the verifier conservative.

The previous version mixed two ideas and got the arithmetic wrong: the shrink path compared the
footprint reach against a clearance that did NOT include `BUILDING_ROAD_CLEARANCE`, while the push
path required `BUILDING_ROAD_CLEARANCE + half_diag`.  The result was that b_37911, with a centre
clearance of +1.489 m and a footprint reach of 5.523 m, satisfied `half_diag > clearance` but the
`allowed` scale came out relative to the wrong quantity, and it shipped at full size still
overlapping by 2.6 m.

ONE RULE NOW
------------
`effective` = distance from the building centre to the nearest road edge, minus the footprint's
rotation-independent reach (its half-diagonal) and minus the required clearance.  `effective >= 0`
means the footprint clears the road whatever its rotation.

* `effective >= 0`  -> fine, leave it.
* `effective < 0` but the centre is clear of the road -> shrink, by exactly the shortfall.
* centre inside the road -> push out by the shortfall.

The verifier is also made conservative: it tests a BOUNDING CIRCLE of radius `half_diag` rather than
four rotated corners.  Corner tests under-report when the model's own axes differ from the TSStatic
rotation, which is what let b_37911 pass unnoticed.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = """            if self.roads:
                clearance = road_clearance(bx, by, self._road_segments) - BUILDING_ROAD_CLEARANCE

                # Footprint reach: the half-diagonal is the worst case once the building is rotated
                # against the road.
                half_diag = 0.5 * math.hypot(model_size[0], model_size[1]) * scale[0]

                if math.isfinite(clearance):
                    if clearance >= 0.0 and half_diag > 1e-6 and half_diag > clearance:
                        # Centre is clear but the footprint still reaches the road: shrink.
                        allowed = min(1.0, clearance / (0.5 * math.hypot(model_size[0], model_size[1])))
                        if allowed < scale[0]:
                            scale = (allowed, allowed, min(scale[2], max(allowed, 1.0)))
                    elif clearance < 0.0:
                        # Centre is INSIDE a road.  Scaling cannot fix this -- a footprint cannot be
                        # shrunk out of a corridor it is centred in -- so the building is pushed out
                        # along the direction away from the road.  CS1 places "Road Connection"
                        # prefabs like this on purpose.
                        moved = push_out_of_road(
                            bx, by, self._road_segments, BUILDING_ROAD_CLEARANCE + half_diag
                        )
                        if moved is not None:
                            bx, by = moved
                            self.report[\"buildingsPushedOffRoad\"] = (
                                self.report.get(\"buildingsPushedOffRoad\", 0) + 1
                            )
                            # Resample: the building now stands somewhere else.
                            ground = self.ground_height(bx, by)"""

NEW = """            if self.roads:
                # rotation-independent footprint reach, unscaled and scaled
                model_half_diag = 0.5 * math.hypot(model_size[0], model_size[1])
                half_diag = model_half_diag * scale[0]

                # Distance from the centre to the nearest road EDGE.  Negative means the centre is
                # inside the road surface itself.
                centre_edge = road_clearance(bx, by, self._road_segments)

                if math.isfinite(centre_edge):
                    # One quantity decides everything: how much room is left once the footprint's
                    # worst-case reach and the required clearance are both accounted for.
                    effective = centre_edge - half_diag - BUILDING_ROAD_CLEARANCE

                    if effective < 0.0:
                        if centre_edge > 0.0 and model_half_diag > 1e-6:
                            # Centre is clear of the road but the footprint reaches it: shrink by
                            # exactly the shortfall, never below a usable size.
                            allowed = max(0.05, (centre_edge - BUILDING_ROAD_CLEARANCE) / model_half_diag)
                            if allowed < scale[0]:
                                scale = (allowed, allowed, min(scale[2], max(allowed, 1.0)))
                                half_diag = model_half_diag * scale[0]
                                effective = centre_edge - half_diag - BUILDING_ROAD_CLEARANCE
                        else:
                            # Centre is INSIDE a road, so scaling cannot help -- a footprint cannot be
                            # shrunk out of a corridor it is centred in.  CS1 places "Road Connection"
                            # and "Water Pipe Junction" prefabs like that on purpose, so the building
                            # is pushed out instead.
                            moved = push_out_of_road(
                                bx, by, self._road_segments,
                                BUILDING_ROAD_CLEARANCE + half_diag,
                            )
                            if moved is not None:
                                bx, by = moved
                                self.report[\"buildingsPushedOffRoad\"] = (
                                    self.report.get(\"buildingsPushedOffRoad\", 0) + 1
                                )
                                # Resample: the building now stands somewhere else.
                                ground = self.ground_height(bx, by)"""

if OLD not in src:
    raise SystemExit("clearance block anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("single rule  :", "effective = centre_edge - half_diag - BUILDING_ROAD_CLEARANCE" in src)
print("shrink path  :", "allowed = max(0.05, (centre_edge - BUILDING_ROAD_CLEARANCE)" in src)

# ---- make the verifier conservative -----------------------------------------------------------
VPATH = os.path.join(REPO, "tools", "dump", "verify_building_clearance.py")
v = io.open(VPATH, encoding="utf-8").read()
v = v.replace(
    '    for ox, oy in ((-half_w, -half_l), (half_w, -half_l), (-half_w, half_l), (half_w, half_l)):\n'
    '        rx = ox * cos_a - oy * sin_a\n'
    '        ry = ox * sin_a + oy * cos_a\n'
    '        px, py = bx + rx, by + ry\n'
    '        d = B.road_clearance(px, py, segments)\n'
    '        if d < best:\n'
    '            best = d\n',
    '    # Bounding circle, not rotated corners: a corner test under-reports when the model axes\n'
    '    # differ from the TSStatic rotation, which is what let an overlapping building pass.\n'
    '    reach = math.hypot(half_w, half_l)\n'
    '    best = B.road_clearance(bx, by, segments) - reach\n',
    1,
)
io.open(VPATH, "w", encoding="utf-8", newline="\n").write(v)
ast.parse(v)
print("verifier updated to a bounding circle; syntax OK")
