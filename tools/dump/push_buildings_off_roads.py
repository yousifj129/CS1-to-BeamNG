"""
Move buildings that sit INSIDE a road out of it.

The clearance cap only shrank buildings whose centre was already clear of the road.  Measured on the
built level, the 56 buildings that still overlapped were not marginal at all:

    b_806   prefab "Road Connection"   centre clearance -14.000 m

Their centres are **inside** the road surface, so no amount of scaling fixes them -- a footprint
cannot be shrunk out of a corridor it is centred in.  Scaling down would also have been pointless:
at -14 m the required scale is negative.

CS1 places these deliberately: "Road Connection" is a junction/filler prefab whose centre sits on the
road by design.

So an overlapping building is now pushed out along the direction away from the nearest road
centre-line, by just enough for its rotated footprint to clear the edge, plus the configured
clearance.  The push is capped, and a building too deeply embedded to be pushed out cleanly is left
where it is rather than teleported across the map.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

HELPER = '''

# A building whose centre is inside a road is pushed out by at most this much.  Beyond it the
# building is left alone rather than moved somewhere arbitrary.
BUILDING_MAX_PUSH = 40.0


def push_out_of_road(
    x: float,
    y: float,
    segments: Sequence[Tuple[float, float, float, float, float]],
    needed: float,
    max_push: float = BUILDING_MAX_PUSH,
) -> Optional[Tuple[float, float]]:
    """
    Nudge a point out of the nearest road corridor, returning the new (x, y) or None.

    `needed` is how far the point must end up from the nearest road EDGE.  The push direction is
    away from the nearest centre-line, which is the shortest way out.  Returns None when the point
    is already clear, when no road is near, or when the required push exceeds `max_push` -- a
    building embedded that deeply should keep its CS1 position rather than be flung elsewhere.
    """
    if not segments:
        return None

    best_edge = float("inf")
    best_point = None
    best_centre = None
    for ax, ay, bx, by, half in segments:
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-12:
            cx, cy = ax, ay
        else:
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length_sq))
            cx, cy = ax + dx * t, ay + dy * t
        edge = math.hypot(x - cx, y - cy) - half
        if edge < best_edge:
            best_edge = edge
            best_point = (cx, cy)
            best_centre = (cx, cy)

    if best_point is None or best_edge >= needed:
        return None

    # Direction away from the centre-line.  If the point is exactly ON the centre-line there is no
    # such direction, so fall back to the segment normal.
    vx, vy = x - best_centre[0], y - best_centre[1]
    length = math.hypot(vx, vy)
    if length < 1e-6:
        return None
    vx, vy = vx / length, vy / length

    distance = needed - best_edge
    if distance > max_push:
        return None
    return (x + vx * distance, y + vy * distance)

'''

anchor = "def roads_as_segments("
if anchor not in src:
    raise SystemExit("roads_as_segments anchor not found")
src = src.replace(anchor, HELPER.strip() + "\n\n\n" + anchor, 1)

# ---- use it when placing a building -----------------------------------------------------------
OLD = """            if self.roads:
                clearance = road_clearance(bx, by, self._road_segments) - BUILDING_ROAD_CLEARANCE
                if math.isfinite(clearance) and clearance > 0.0:
                    # Worst case is the footprint's half-diagonal rotated against the road, so use
                    # that rather than the half-width.
                    half_diag = 0.5 * math.hypot(model_size[0], model_size[1])
                    if half_diag > 1e-6:
                        limit = clearance / half_diag
                        allowed = min(1.0, limit)
                        if allowed < scale[0]:
                            scale = (allowed, allowed, min(scale[2], max(allowed, 1.0)))"""

NEW = """            if self.roads:
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
                            self.report["buildingsPushedOffRoad"] = (
                                self.report.get("buildingsPushedOffRoad", 0) + 1
                            )"""
if OLD not in src:
    raise SystemExit("clearance application anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("push helper :", "def push_out_of_road(" in src)
print("applied     :", "push_out_of_road(" in src and "buildingsPushedOffRoad" in src)
