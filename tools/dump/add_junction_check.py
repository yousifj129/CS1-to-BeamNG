"""Add a junction-connectivity check, then document."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

if "chain endpoints meet another chain" in src:
    print("already present")
    raise SystemExit(0)

BLOCK = '''# ---------------------------------------------------------------- junction connectivity
# The check that would have caught the junction bug immediately.  Source nodes shared by two roads
# agree to 0.000 m, so a chain endpoint should land exactly on another chain.  Emitting geometry
# from the Bezier instead of the node left every chain stopping short: 0 of 111 junctions had an
# endpoint on them, the closest being 2 m away and the median 10 m.
if roads:
    def _seg_dist(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-12:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
        return math.hypot(px - (ax + dx * t), py - (ay + dy * t))

    def _dist_to_road(px, py, road):
        nodes = road["nodes"]
        return min(
            _seg_dist(px, py, nodes[i][0], nodes[i][1], nodes[i + 1][0], nodes[i + 1][1])
            for i in range(len(nodes) - 1)
        )

    endpoints = []
    for index, road in enumerate(roads):
        endpoints.append((index, road["nodes"][0]))
        endpoints.append((index, road["nodes"][-1]))

    joined = 0
    for ri, node in endpoints:
        best = min(
            (_dist_to_road(node[0], node[1], other) for rj, other in enumerate(roads) if rj != ri),
            default=float("inf"),
        )
        if best <= 0.01:
            joined += 1

    # Dead ends at the map edge are legitimate, so this is a proportion rather than all.
    ratio = joined / max(1, len(endpoints))
    check(ratio >= 0.5,
          "chain endpoints meet another chain (shared nodes agree to 0.000 m in the source)",
          f"{joined}/{len(endpoints)} endpoints joined = {ratio * 100:.0f}%")

'''

anchor = "# ================================================================ lighting"
if anchor not in src:
    raise SystemExit("lighting anchor not found")
src = src.replace(anchor, BLOCK + anchor, 1)

# `math` is needed by the block.
if "\nimport math\n" not in src:
    src = src.replace("import json\n", "import json\nimport math\n", 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("added the junction-connectivity check; syntax OK")
