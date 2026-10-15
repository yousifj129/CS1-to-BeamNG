"""Move the terrain-tiling checks into the material-block scope where `m` is available."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance_report.py")
src = io.open(PATH, encoding="utf-8").read()

# Cut the misplaced block out.
start = src.index("# ---------------------------------------------------------------- terrain tiling")
end = src.index("        check(field in m, f\"{field} declared (tiling depends on it)\")") + len(
    "        check(field in m, f\"{field} declared (tiling depends on it)\")"
)
block = src[start:end]
src = src[:start] + src[end:]

# Re-indent from 4 to 8 spaces and place it inside the material block, right before the
# TerrainBlock section begins.
indented = "\n".join(
    ("    " + line) if line.strip() else line for line in block.split("\n")
)
anchor = "# ---------------------------------------------------------------- rule: TerrainBlock"
if anchor not in src:
    raise SystemExit("TerrainBlock section anchor not found")
src = src.replace(anchor, indented + "\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)

import ast

ast.parse(src)
print("moved the tiling checks; syntax OK")
