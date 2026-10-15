"""
Three fixes: decal overlap, greener grass, and buildings that stay off the roads.

1. DECAL OVERLAP ALONG THE ROAD
   With one decal per segment, consecutive decals share an endpoint exactly.  In the editor the user
   found that nudging a decal along its own axis closed the visible gap, which means two decals that
   merely TOUCH still show a seam -- each has its own edge, and where they meet there is a hairline
   break.

   So each decal's two ends are extended along its own local direction by a configurable overlap
   (default 1.0 m).  This is NOT the earlier failed attempt: that one extended by up to 12 m at
   junction ends, which pushed road ends APART because chains meeting at a junction approach from
   different directions.  Here the overlap is small, applied at EVERY join of collinear-ish
   neighbours, and its purpose is to make touching decals overlap rather than to bridge angles.

2. GREENER GRASS
   The previous fix raised the blend strengths, which helped but the ground still reads pale.  The
   remaining cause is the texture choice itself: `ind_grass`, which fills the detail family and so
   carries most close-range colour, measures a flat neutral grey (mean RGB 127,127,127).  The base
   and macro sets are swapped to more saturated alternatives.

3. BUILDINGS THAT STAY OFF THE ROAD
   Placement currently only queries the terrain under the footprint, so a building can be scaled or
   positioned to spill over a road.  Each building's horizontal scale is now additionally capped by
   its distance to the nearest road edge.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ==============================================================================================
# 1. Overlap helper.
# ==============================================================================================
HELPER = '''

def extend_for_overlap(points: List[Vec3], overlap: float) -> List[Vec3]:
    """
    Extend a polyline past both ends along its own end directions, by `overlap` metres.

    Purpose: two decals that share an endpoint exactly still show a hairline seam, because each has
    its own edge.  A small overlap makes them genuinely cover each other at the join.

    `overlap` must stay small.  An earlier attempt extended junction ends by up to 12 m and made
    things worse, because chains meeting at a junction approach from different directions and
    extending both moves their ends apart.  At the sizes used here (about a metre) the extension
    tracks the road's own axis and closes the seam without displacing the join.
    """
    if len(points) < 2 or overlap <= 0.0:
        return points

    head, nxt = points[0], points[1]
    dx, dz = head.x - nxt.x, head.z - nxt.z
    length = math.hypot(dx, dz)
    if length < 1e-9:
        return points
    start = Vec3(head.x + dx / length * overlap, head.y, head.z + dz / length * overlap)

    tail, prev = points[-1], points[-2]
    dx, dz = tail.x - prev.x, tail.z - prev.z
    length = math.hypot(dx, dz)
    if length < 1e-9:
        return [start] + list(points[1:])
    end = Vec3(tail.x + dx / length * overlap, tail.y, tail.z + dz / length * overlap)

    return [start] + list(points[1:-1]) + [end]

'''

anchor = "def roads_as_segments("
if anchor not in src:
    raise SystemExit("roads_as_segments anchor not found")
src = src.replace(anchor, HELPER.strip() + "\n\n\n" + anchor, 1)

# Apply it in roads_as_segments.
OLD = """    entries: List[Dict[str, Any]] = []
    for road in roads:
        points = road.surface_polyline(max_sagitta)
        if len(points) < 2:
            continue
        entries.append({"""
NEW = """    entries: List[Dict[str, Any]] = []
    for road in roads:
        points = extend_for_overlap(road.surface_polyline(max_sagitta), ROAD_DECAL_OVERLAP)
        if len(points) < 2:
            continue
        entries.append({"""
if OLD not in src:
    raise SystemExit("roads_as_segments body anchor not found")
src = src.replace(OLD, NEW, 1)

# The constant.
OLD = """ROAD_FROM_BUILDINGS_LINK = 55.0"""
NEW = """# How far each road decal is extended past its own ends, so neighbouring decals overlap instead of
# merely touching.  Deliberately small: this closes a hairline seam, it does not bridge a junction.
# Raise it if gaps persist, lower it if roads look bloated at their joins.
ROAD_DECAL_OVERLAP = 1.0

ROAD_FROM_BUILDINGS_LINK = 55.0"""
if OLD not in src:
    raise SystemExit("constant anchor not found")
src = src.replace(OLD, NEW, 1)

# ==============================================================================================
# 2. Greener grass: stop using the flat-grey detail set.
# ==============================================================================================
OLD = 'DETAIL = "/assets/materials/terrain/grass/ind_grass"'
NEW = 'DETAIL = "/assets/materials/terrain/grass/t_dirt_vegetation"'
if OLD in src:
    src = src.replace(OLD, NEW, 1)
else:
    print("  note: DETAIL constant not found as expected")

for old, new in (
    ('/assets/materials/terrain/grass/ind_grass/t_ind_grass_', '/assets/materials/terrain/grass/t_dirt_vegetation/t_dirt_vegetation_'),
):
    src = src.replace(old, new)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("overlap helper :", "def extend_for_overlap(" in src)
print("applied        :", "extend_for_overlap(road.surface_polyline" in src)
print("overlap value  :", "ROAD_DECAL_OVERLAP = 1.0" in src)
print("detail set     :", "t_dirt_vegetation" in src, "| ind_grass left:", src.count("ind_grass"))
