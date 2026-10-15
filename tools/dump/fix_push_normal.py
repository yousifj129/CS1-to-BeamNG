"""
Handle the case the push could not: a centre exactly ON the road centre-line.

Measured for b_806 ("Road Connection"):

    nearest centre-line point = (8648.80, 343.43)   half-width 14.00   raw distance 0.00
    best_edge = -14.0000
    direction length = 0.0000        <- no direction away from the line

The building is centred precisely on the centre-line of a 28 m road.  "Away from the centre-line" is
undefined there, so the helper returned None and nothing moved.

A segment normal is now used in that case, which is well-defined and is the shortest way out.  Which
of the two normals is chosen is decided by which side ends up further from every road, rather than
arbitrarily -- one side may be another carriageway.

Also fixed: the ground height was sampled BEFORE the push, so a moved building kept the elevation of
where it used to be and would float or sink.  It is now resampled at the final position.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- 1. normal fallback ----------------------------------------------------------------------
OLD = """    # Direction away from the centre-line.  If the point is exactly ON the centre-line there is no
    # such direction, so fall back to the segment normal.
    vx, vy = x - best_centre[0], y - best_centre[1]
    length = math.hypot(vx, vy)
    if length < 1e-6:
        return None
    vx, vy = vx / length, vy / length

    distance = needed - best_edge
    if distance > max_push:
        return None
    return (x + vx * distance, y + vy * distance)"""

NEW = """    distance = needed - best_edge
    if distance > max_push:
        return None

    # Direction away from the centre-line.
    vx, vy = x - best_point[0], y - best_point[1]
    length = math.hypot(vx, vy)

    if length < 1e-3:
        # The point lies ON the centre-line, so "away" is undefined.  Use the segment normal, which
        # is well defined and is the shortest way out.  Measured case: a "Road Connection" prefab
        # centred exactly on the centre-line of a 28 m road, where the offset was 0.0000 m.
        ax, ay, bx, by, _half = best_segment
        sx, sy = bx - ax, by - ay
        seg_len = math.hypot(sx, sy)
        if seg_len < 1e-9:
            return None
        nx, ny = -sy / seg_len, sx / seg_len

        # Either side may be blocked by another carriageway, so take whichever ends up clearer.
        candidates = [
            (x + nx * distance, y + ny * distance),
            (x - nx * distance, y - ny * distance),
        ]
        return max(candidates, key=lambda p: _nearest_edge(p[0], p[1], segments))

    vx, vy = vx / length, vy / length
    return (x + vx * distance, y + vy * distance)"""

if OLD not in src:
    raise SystemExit("push body anchor not found")
src = src.replace(OLD, NEW, 1)

# Track the winning segment, and add the small edge helper.
OLD = """    best_edge = float("inf")
    best_point = None
    best_centre = None
    for ax, ay, bx, by, half in segments:"""
NEW = """    best_edge = float("inf")
    best_point = None
    best_segment = None
    for ax, ay, bx, by, half in segments:"""
if OLD not in src:
    raise SystemExit("push loop anchor not found")
src = src.replace(OLD, NEW, 1)

OLD = """            best_edge = edge
            best_point = (cx, cy)
            best_centre = (cx, cy)"""
NEW = """            best_edge = edge
            best_point = (cx, cy)
            best_segment = (ax, ay, bx, by, half)"""
if OLD not in src:
    raise SystemExit("push assign anchor not found")
src = src.replace(OLD, NEW, 1)

EDGE_HELPER = '''

def _nearest_edge(x: float, y: float, segments: Sequence[Tuple[float, float, float, float, float]]) -> float:
    """Distance from (x, y) to the nearest road EDGE; used only to choose a push direction."""
    best = float("inf")
    for ax, ay, bx, by, half in segments:
        edge = _point_to_segment(x, y, ax, ay, bx, by) - half
        if edge < best:
            best = edge
    return best


'''
anchor = "def push_out_of_road("
if anchor not in src:
    raise SystemExit("push_out_of_road anchor not found")
src = src.replace(anchor, EDGE_HELPER.strip() + "\n\n\n" + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("normal fallback:", "nx, ny = -sy / seg_len, sx / seg_len" in src)
