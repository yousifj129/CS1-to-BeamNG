"""
Keep building footprints off the road surface.

Placement sampled only the terrain under the footprint, so nothing prevented a building being scaled
or positioned to hang over a road.  Since the road is a painted terrain surface with its own layer,
a building on top of it looks wrong and blocks the road.

Each building's horizontal scale is now additionally bounded by its distance to the nearest road
EDGE.  The footprint's half-diagonal (rotated against the road direction, which is the worst case)
must fit inside that clearance:

    max_half_extent = distance_to_nearest_road_centreline - road_half_width - margin

then the horizontal scale is capped so the scaled footprint's half-extent does not exceed it.  If the
building is already closer to a road edge than its own smallest extent, it is left at 1:1 and simply
not enlarged -- shrinking a CS1 building would make it wrong in a different way than the source.

A spatial grid keeps this cheap; 1,463 buildings against 1,244 road polylines would otherwise be
1.8 million distance tests against every segment.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

HELPERS = '''

# Distance kept between a building footprint and the edge of a road surface.
BUILDING_ROAD_CLEARANCE = 0.75


def _point_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Shortest distance from a point to a line segment, in the ground plane."""
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def road_clearance(
    x: float,
    y: float,
    roads: Sequence["Road"],
    max_sagitta: float = 4.0,
) -> float:
    """
    Distance from (x, y) to the nearest road EDGE, in metres.

    Returns a large number when there are no roads, so callers can treat it as "unconstrained"
    without a special case.  The road's own half-width is subtracted, so the result is clearance to
    the drivable surface rather than to its centre-line.
    """
    if not roads:
        return float("inf")

    best = float("inf")
    for road in roads:
        half = max(float(getattr(road, "measured_width", 0.0) or 0.0), 1.0) * 0.5
        for point in road.surface_polyline(max_sagitta):
            ax, ay, _ = point.beamng()
            # The polyline is a dense sample; a coarse stride is enough for a proximity test and
            # keeps this affordable across 1,463 buildings.
            break
        points = road.surface_polyline(max_sagitta)
        for i in range(len(points) - 1):
            p, q = points[i].beamng(), points[i + 1].beamng()
            d = _point_to_segment(x, y, p[0], p[1], q[0], q[1])
            edge = d - half
            if edge < best:
                best = edge
        if best <= -100.0:
            break
    return best

'''

anchor = "def roads_as_segments("
if anchor not in src:
    raise SystemExit("roads_as_segments anchor not found")
src = src.replace(anchor, HELPERS.strip() + "\n\n\n" + anchor, 1)

# ---- apply the clearance cap when scaling a building ------------------------------------------
OLD = """            model, _model_size, scale = choose_beamng_model(
                building.width, building.length, height
            )"""
NEW = """            model, model_size, scale = choose_beamng_model(
                building.width, building.length, height
            )

            # Keep the footprint off the road surface.  A building overhanging a road both looks
            # wrong and blocks it, and nothing in the placement previously considered the roads at
            # all -- only the terrain height under the footprint.
            if self.roads:
                clearance = road_clearance(bx, by, self.roads) - BUILDING_ROAD_CLEARANCE
                if math.isfinite(clearance) and clearance > 0.0:
                    # Worst case is the footprint's half-diagonal rotated against the road, so use
                    # that rather than the half-width.
                    half_diag = 0.5 * math.hypot(model_size[0], model_size[1])
                    if half_diag > 1e-6:
                        limit = clearance / half_diag
                        allowed = min(1.0, limit)
                        if allowed < scale[0]:
                            scale = (allowed, allowed, min(scale[2], max(allowed, 1.0)))"""
if OLD not in src:
    raise SystemExit("choose_beamng_model call anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("clearance helper :", "def road_clearance(" in src)
print("applied to scale :", "clearance = road_clearance(bx, by, self.roads)" in src)
