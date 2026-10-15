"""Move the terrain-constants block from the top of the file back to where it belongs."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# The block currently sits before the shebang.  Cut it out.
marker = "}"
start = src.index('_TERRAIN = "/assets/materials/terrain"')
end = src.index("\n", src.index("heightMacroTex", start))
block = src[start:end].rstrip()

# Remove the misplaced copy, leaving the shebang first.
src = src[:start] + src[end:].lstrip("\n")

# Re-insert it immediately before emit_terrain_materials.
anchor = "    def emit_terrain_materials(self) -> None:"
if anchor not in src:
    raise SystemExit("emit_terrain_materials anchor not found")
src = src.replace(anchor, block + "\n\n\n" + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)

lines = src.split("\n")
print("first line:", repr(lines[0]))
print("block present once:", src.count('_TERRAIN = "/assets/materials/terrain"'))
print("block before method:", src.index(block) < src.index(anchor))
print("grass refs:", src.count("grass/ind_grass/t_ind_grass_b.png"))
