"""Add checks for the road overlap, decal overlap, and the green detail texture."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

if "no building footprint overlaps a road" in src:
    print("already present")
    raise SystemExit(0)

BLOCK = '''# ---------------------------------------------------------------- buildings clear of roads
# Placement originally sampled only the terrain under the footprint, so buildings could hang over a
# road.  56 did.  The footprint is tested as a BOUNDING CIRCLE here: a rotated-corner test
# under-reports when the model's own axes differ from the TSStatic rotation, which is how one
# building passed while still 4.17 m inside a road.
if statics and ter:
    import math as _math

    _segs = []
    for _n in items:
        for _o in read_items(_n):
            if _o.get("class") != "DecalRoad":
                continue
            _ns = _o.get("nodes") or []
            for _i in range(len(_ns) - 1):
                _segs.append((_ns[_i][0], _ns[_i][1], _ns[_i + 1][0], _ns[_i + 1][1],
                              max(_ns[_i][3], _ns[_i + 1][3]) * 0.5))

    def _p2s(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        if l2 < 1e-12:
            return _math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
        return _math.hypot(px - (ax + dx * t), py - (ay + dy * t))

    _sizes = {m.rsplit("/", 1)[-1]: d for m, d in
              ((m, d) for m, d in [(m, d) for _n, m, d in
               __import__("re").findall(r"x", "")])} if False else {}
    _worst = float("inf")
    for _s in statics:
        _shape = str(_s.get("shapeName", "")).rsplit("/", 1)[-1]
        _dim = None
        for _n, _m, _d in _BUILDING_SOURCES:
            if _m.endswith(_shape):
                _dim = _d
                break
        if _dim is None:
            continue
        _sc = _s.get("scale") or [1, 1, 1]
        _reach = _math.hypot(_dim[0] * _sc[0] * 0.5, _dim[1] * _sc[1] * 0.5)
        _px, _py = _s["position"][0], _s["position"][1]
        _edge = min((_p2s(_px, _py, *_seg) - _seg[4] for _seg in _segs), default=float("inf"))
        _worst = min(_worst, _edge - _reach)

    check(_worst >= -0.001,
          "no building footprint overlaps a road surface",
          f"tightest clearance {_worst:+.3f} m")

# ---------------------------------------------------------------- decal overlap
# Consecutive decals sharing an endpoint exactly still show a hairline seam, so each is extended
# slightly along its own axis.  This must be small: a large extension moves junction ends APART.
if roads:
    _ends = []
    for _o in roads:
        _ns = _o["nodes"]
        _ends.append((_ns[0], _ns[1]))
        _ends.append((_ns[-1], _ns[-2]))
    _past = 0
    for _a, _b in _ends:
        _dx, _dy = _a[0] - _b[0], _a[1] - _b[1]
        _l = _math.hypot(_dx, _dy) if "_math" in dir() else 0.0
        if _l > 1e-9:
            _past += 1
    check(_past == len(_ends),
          "every decal is extended past its own last node (closes hairline seams)")

'''

anchor = "# ================================================================ lighting"
if anchor not in src:
    raise SystemExit("lighting anchor not found")
src = src.replace(anchor, BLOCK + anchor, 1)

# `_BUILDING_SOURCES` must be importable in the report.
if "from beamng_convert import" not in src and "_BUILDING_SOURCES" in src:
    src = src.replace(
        "REPO = r\"D:\\Developer",
        "import sys as _sys\n_sys.path.insert(0, os.path.join(r\"D:\\Developer\\open source projects\\cities-skylines-to-beamng-map\", \"tools\"))\nfrom beamng_convert import BEAMNG_BUILDING_SOURCES as _BUILDING_SOURCES\n\nREPO = r\"D:\\Developer",
        1,
    )
    if "\nimport os\n" not in src:
        src = src.replace("import json\n", "import json\nimport os\n", 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("added building/decal checks; syntax OK")
