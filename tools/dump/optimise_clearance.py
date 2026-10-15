"""Remove dead code from road_clearance and precompute the road segments once.

The first version called `road.surface_polyline()` inside the per-building loop, so 1,463 buildings
each re-flattened 1,244 road Beziers -- roughly 1.8 million segment distance tests with the
flattening repeated every time.  The segments are now computed once and reused.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("def road_clearance(")
end = src.index("\n\n\n", start)

NEW = '''def road_segments(roads: Sequence["Road"], max_sagitta: float = 4.0) -> List[Tuple[float, float, float, float, float]]:
    """
    Flatten every road once into (ax, ay, bx, by, half_width) tuples.

    Precomputed because `road_clearance` is called per building: flattening 1,244 Beziers inside
    that loop would repeat the same work 1,463 times.
    """
    segments: List[Tuple[float, float, float, float, float]] = []
    for road in roads:
        half = max(float(getattr(road, "measured_width", 0.0) or 0.0), 1.0) * 0.5
        points = road.surface_polyline(max_sagitta)
        for i in range(len(points) - 1):
            p = points[i].beamng()
            q = points[i + 1].beamng()
            segments.append((p[0], p[1], q[0], q[1], half))
    return segments


def road_clearance(
    x: float,
    y: float,
    segments: Sequence[Tuple[float, float, float, float, float]],
) -> float:
    """
    Distance from (x, y) to the nearest road EDGE, in metres.

    The road's own half-width is subtracted, so this is clearance to the drivable surface rather
    than to its centre-line.  Returns infinity when there are no segments, so callers can treat
    that as "unconstrained" without a special case.
    """
    if not segments:
        return float("inf")

    best = float("inf")
    for ax, ay, bx, by, half in segments:
        edge = _point_to_segment(x, y, ax, ay, bx, by) - half
        if edge < best:
            best = edge
            if best <= 0.0:
                # Already overlapping a road; no need to look further.
                return best
    return best'''

src = src[:start] + NEW + src[end:]

# ---- use the precomputed segments -------------------------------------------------------------
OLD = """                clearance = road_clearance(bx, by, self.roads) - BUILDING_ROAD_CLEARANCE"""
NEW = """                clearance = road_clearance(bx, by, self._road_segments) - BUILDING_ROAD_CLEARANCE"""
if OLD not in src:
    raise SystemExit("clearance call anchor not found")
src = src.replace(OLD, NEW, 1)

# Build the segment list once, lazily.
OLD = """    def emit_buildings(self) -> None:"""
NEW = """    def _building_road_segments(self):
        \"\"\"Flatten the roads once, for reuse across every building.\"\"\"
        if getattr(self, "_road_segments", None) is None:
            self._road_segments = road_segments(self.roads)
        return self._road_segments

    def emit_buildings(self) -> None:"""
if OLD not in src:
    raise SystemExit("emit_buildings anchor not found")
src = src.replace(OLD, NEW, 1)

OLD = """        objects: List[Dict[str, Any]] = []

        for building in self.buildings:"""
NEW = """        objects: List[Dict[str, Any]] = []
        self._road_segments = self._building_road_segments()

        for building in self.buildings:"""
if OLD not in src:
    raise SystemExit("emit_buildings body anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("road_segments precomputed:", "def road_segments(" in src)
print("uses cached list         :", "self._road_segments" in src)
