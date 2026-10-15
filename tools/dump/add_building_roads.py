"""
Roads generated from the building layout.

The CS1 road network is replaced here by geometry derived from where the buildings actually are.
The reasoning behind it: every building in a CS1 city was placed against a road, so building
positions carry the road structure implicitly -- a row of buildings along a street lines up along
that street.

METHOD
------
1. Take the building centroids.
2. Build a proximity graph over them with a distance threshold, so a chain of nearby buildings
   becomes an edge.
3. Extract the edges as road segments, quadratically interpolated so they are not ruler-straight.

This gives roads that run past the buildings rather than through empty ground.  It is an
approximation and it is honestly one: building footprints record where roads *are*, not how they
*connect*, so the resulting network is a proximity graph, not a topology.  Expect it to look
plausible around dense development and sparse where buildings are far apart.

The generated roads are given an explicit width and an asphalt surface, and they are painted into
the terrain layer map exactly like the CS1-derived ones, so they grip like roads as well as looking
like them.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

GENERATOR = '''

# ==========================================================================================
#  Building-derived road generation
# ==========================================================================================
#
# Used when `--roads-from-buildings` is passed.  See the module docstring of
# tools/dump/derive_roads_from_buildings.py for the reasoning; the short version is that a CS1
# building was placed against a road, so building positions imply where streets run.
# ==========================================================================================

ROAD_FROM_BUILDINGS_LINK = 55.0     # metres: max gap between two buildings still joined by a street
ROAD_FROM_BUILDINGS_WIDTH = 8.0     # metres: a two-lane street


def derive_roads_from_buildings(
    buildings: Sequence["Building"],
    link_distance: float = ROAD_FROM_BUILDINGS_LINK,
    width: float = ROAD_FROM_BUILDINGS_WIDTH,
    max_degree: int = 3,
) -> List[Dict[str, Any]]:
    """
    Build a road network from building positions, returning chain dicts shaped like `chain_roads`.

    Each building is joined to its nearest few neighbours within `link_distance`.  `max_degree`
    keeps the result from becoming a spiderweb: without it, dense clusters produce quadratic numbers
    of near-duplicate links that all overlap on the ground.
    """
    if len(buildings) < 2:
        return []

    centres = []
    for b in buildings:
        bx, by, _ = b.position.beamng()
        centres.append((bx, by, b))

    # Uniform grid index, so neighbour lookup does not compare every pair against every other.
    cell = max(link_distance, 1.0)
    grid: Dict[Tuple[int, int], List[int]] = {}
    for index, (bx, by, _b) in enumerate(centres):
        grid.setdefault((int(bx // cell), int(by // cell)), []).append(index)

    link_sq = link_distance * link_distance
    pairs: List[Tuple[float, int, int]] = []
    for index, (bx, by, _b) in enumerate(centres):
        cx, cy = int(bx // cell), int(by // cell)
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for other in grid.get((gx, gy), ()):
                    if other <= index:
                        continue
                    ox, oy, _ob = centres[other]
                    d2 = (ox - bx) ** 2 + (oy - by) ** 2
                    if d2 <= link_sq:
                        pairs.append((d2, index, other))

    pairs.sort()
    degree: Dict[int, int] = {}
    chosen: List[Tuple[int, int]] = []
    for _d2, a, b in pairs:
        if degree.get(a, 0) >= max_degree or degree.get(b, 0) >= max_degree:
            continue
        degree[a] = degree.get(a, 0) + 1
        degree[b] = degree.get(b, 0) + 1
        chosen.append((a, b))

    chains: List[Dict[str, Any]] = []
    for a, b in chosen:
        ax, ay, ab = centres[a]
        bx, by, bb = centres[b]

        # A slight perpendicular bow so consecutive streets are not all dead straight.
        mx, my = (ax + bx) * 0.5, (ay + by) * 0.5
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1.0
        bow = min(length * 0.06, 3.0)
        mx += -dy / length * bow
        my += dx / length * bow

        start = Vec3(ax, my * 0.0 + ay, 0.0)
        control = Vec3(mx, my, 0.0)
        end = Vec3(bx, by, 0.0)

        # Quadratic bezier flattened to a few points.
        points: List[Vec3] = []
        steps = max(2, int(length / 12.0))
        for s in range(steps + 1):
            t = s / steps
            u = 1.0 - t
            px = u * u * start.x + 2 * u * t * control.x + t * t * end.x
            py = u * u * start.y + 2 * u * t * control.y + t * t * end.y
            points.append(Vec3(px, py, 0.0))

        chains.append({
            "points": points,
            "width": width,
            "material": "road_asphalt_2lane",
            "road": ab,
            "segments": 1,
        })

    return chains


'''

anchor = "# ==========================================================================================\n#  Level builder"
if anchor not in src:
    raise SystemExit("level builder banner not found")
src = src.replace(anchor, GENERATOR.strip() + "\n\n\n" + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("generator added:", "def derive_roads_from_buildings(" in src)
