"""Insert a clean building-clearance check into the conformance report."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

if "no building footprint overlaps a road" in src:
    print("already present")
    raise SystemExit(0)

# Add the import of the building shape table near the top.
if "BUILDING_SOURCES" not in src:
    src = src.replace(
        'REPO = r"D:\\Developer',
        'import sys as _sys\n'
        '_sys.path.insert(0, r"D:\\Developer\\open source projects\\cities-skylines-to-beamng-map\\tools")\n'
        'from beamng_convert import BEAMNG_BUILDING_SOURCES\n\n'
        'REPO = r"D:\\Developer',
        1,
    )

BLOCK = '''# ---------------------------------------------------------------- buildings clear of roads
# Placement originally sampled only the terrain under the footprint, so a building could hang over a
# road; 56 did.  The footprint is tested as a BOUNDING CIRCLE, because a rotated-corner test
# under-reports when the model's own axes differ from the TSStatic rotation -- one building passed a
# corner test while still 4.17 m inside a road.
if statics:
    road_segments = []
    for _o in roads:
        _ns = _o.get("nodes") or []
        for _i in range(len(_ns) - 1):
            road_segments.append((
                _ns[_i][0], _ns[_i][1], _ns[_i + 1][0], _ns[_i + 1][1],
                max(_ns[_i][3], _ns[_i + 1][3]) * 0.5,
            ))

    def _seg_dist(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        if l2 < 1e-12:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
        return math.hypot(px - (ax + dx * t), py - (ay + dy * t))

    shape_sizes = {}
    for _member, _dims in BEAMNG_BUILDING_SOURCES:
        shape_sizes[_member.rsplit("/", 1)[-1]] = _dims

    tightest = float("inf")
    for _s in statics:
        shape = str(_s.get("shapeName", "")).rsplit("/", 1)[-1]
        dims = shape_sizes.get(shape)
        if dims is None:
            continue
        sc = _s.get("scale") or [1, 1, 1]
        reach = math.hypot(dims[0] * sc[0] * 0.5, dims[1] * sc[1] * 0.5)
        px, py = _s["position"][0], _s["position"][1]
        edge = min(
            (_seg_dist(px, py, *seg[:4]) - seg[4] for seg in road_segments),
            default=float("inf"),
        )
        tightest = min(tightest, edge - reach)

    if tightest < float("inf"):
        check(tightest >= -0.001,
              "no building footprint overlaps a road surface",
              f"tightest clearance {tightest:+.3f} m")

'''

anchor = "# ================================================================ lighting"
if anchor not in src:
    raise SystemExit("lighting anchor not found")
src = src.replace(anchor, BLOCK + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("inserted the building-clearance check; syntax OK")
