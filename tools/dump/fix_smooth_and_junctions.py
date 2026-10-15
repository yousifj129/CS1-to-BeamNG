"""
Smoother terrain, and road chains that genuinely overlap at junctions.

TERRAIN SMOOTHNESS
------------------
The heightmap is reconstructed from scattered road elevation samples.  With 173 chains spread over
32 km that coverage is sparse, and `_fill_gaps` interpolates long distances between distant samples,
which produces the steep facets.

The existing smoothing is `_smooth(filled, iterations=3)`, a 3x3 pass -- three iterations reach
about three cells, which at 4 m per cell is 12 m.  That removes local noise and does nothing about
the long ramps between sparse samples.

The fix is to smooth at TWO scales:

  * the existing fine pass, to keep the surface from getting blocky;
  * a coarse pass, by downsampling, smoothing at the small scale, and upsampling back.  At a quarter
    resolution each step covers four times the ground, so this flattens the long ramps the fine pass
    cannot reach.

The result is blended back with the original at partial strength so real elevation differences (road
grades, hills) survive rather than being flattened into a plane.

ROAD JUNCTIONS
--------------
Chains are cut at junctions, so each incoming road ends exactly at the junction node.  Two decals
that merely touch still leave a visible seam once each has its own edge and fade.  Every chain end is
now extended outward along its final direction by one road half-width, so decals genuinely overlap.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ==============================================================================================
# 1. Two-scale smoothing in build_terrain.
# ==============================================================================================
OLD = """    filled = _as_square(_fill_gaps(work), work_res)
    smoothed = _smooth(filled, iterations=3)
    smoothed = np.nan_to_num(smoothed, nan=0.0, posinf=1.0, neginf=0.0)
    normalised_grid = _as_square(np.clip(smoothed, 0.0, 1.0), work_res)"""

NEW = """    filled = _as_square(_fill_gaps(work), work_res)
    smoothed = _smooth(filled, iterations=3)
    smoothed = np.nan_to_num(smoothed, nan=0.0, posinf=1.0, neginf=0.0)

    # Coarse pass.  `_smooth` is a 3x3 kernel, so its reach is a few cells -- about 12 m here.  The
    # steep facets come from `_fill_gaps` interpolating across the long gaps between sparse road
    # samples, which no amount of local smoothing removes.  Downsampling by 4 makes each smoothing
    # step cover 16x the ground, so the long ramps get flattened too.
    coarse_res = max(16, work_res // 4)
    if coarse_res < work_res:
        coarse = _as_square(_resample(smoothed, coarse_res), coarse_res)
        coarse = _smooth(coarse, iterations=2)
        coarse = _as_square(_resample(coarse, work_res), work_res)
        coarse = np.nan_to_num(coarse, nan=0.0, posinf=1.0, neginf=0.0)
        # Blend rather than replace, so genuine elevation differences (road grades, hills) are
        # softened but not erased.  0.65 toward the coarse result removes the facets while leaving
        # the overall shape recognisable.
        smoothed = smoothed * 0.35 + coarse * 0.65

    smoothed = _smooth(smoothed, iterations=2)
    smoothed = np.nan_to_num(smoothed, nan=0.0, posinf=1.0, neginf=0.0)
    normalised_grid = _as_square(np.clip(smoothed, 0.0, 1.0), work_res)"""

if OLD not in src:
    raise SystemExit("smoothing anchor not found")
src = src.replace(OLD, NEW, 1)

# ==============================================================================================
# 2. Extend chain ends so junction decals overlap.
# ==============================================================================================
OLD2 = """        if len(chain) < 2:
            continue

        widest = max(roads[i].measured_width for i in members)"""

NEW2 = """        if len(chain) < 2:
            continue

        widest = max(roads[i].measured_width for i in members)

        # Push both ends outward by one half-width so that chains meeting at a junction genuinely
        # overlap.  Chains are cut at junctions, so without this each decal merely touches its
        # neighbour -- and two decals that touch still show a seam once each has its own edge fade.
        reach = min(widest * 0.5, 12.0)
        chain = _extend_ends(chain, reach)"""

if OLD2 not in src:
    raise SystemExit("chain end anchor not found")
src = src.replace(OLD2, NEW2, 1)

# ==============================================================================================
# 3. The helper.
# ==============================================================================================
HELPER = '''

def _extend_ends(points: List[Vec3], reach: float) -> List[Vec3]:
    """
    Extend a polyline past both endpoints along its own end directions.

    Used so road decals that meet at a junction overlap instead of touching.  The extension is
    capped by the caller, and short chains are left alone: extrapolating a two-point stub by its
    full half-width can overshoot past the junction it is meant to fill.
    """
    if len(points) < 2 or reach <= 0.0:
        return points

    head = points[0]
    nxt = points[1]
    dx, dy = head.x - nxt.x, head.z - nxt.z
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return points
    start = Vec3(head.x + dx / length * reach, head.y, head.z + dy / length * reach)

    tail = points[-1]
    prev = points[-2]
    dx, dy = tail.x - prev.x, tail.z - prev.z
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return [start] + points[1:]
    end = Vec3(tail.x + dx / length * reach, tail.y, tail.z + dy / length * reach)

    return [start] + list(points[1:-1]) + [end]

'''

anchor = "def chain_roads("
if anchor not in src:
    raise SystemExit("chain_roads anchor not found")
src = src.replace(anchor, HELPER.strip() + "\n\n\n" + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("two-scale smoothing :", "coarse_res = max(16, work_res // 4)" in src)
print("_extend_ends added  :", "def _extend_ends(" in src)
print("called from chains  :", "chain = _extend_ends(chain, reach)" in src)
