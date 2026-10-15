"""Fix the indentation of emit_terrain_materials by inspecting raw leading whitespace."""

import io
import os

PATH = r"D:\Developer\open source projects\cities-skylines-to-beamng-map\tools\beamng_convert.py"
raw = io.open(PATH, encoding="utf-8", newline="").read()
lines = raw.split("\n")

start = next(i for i, l in enumerate(lines) if l.strip().startswith("def emit_terrain_materials(self)"))
end = next(i for i, l in enumerate(lines) if i > start and l.strip().startswith("def emit_preview_image"))

print(f"method lines {start + 1}..{end}")
print("raw leading whitespace per line:")
for i in range(start, min(start + 12, end)):
    leading = len(lines[i]) - len(lines[i].lstrip(" "))
    print(f"  {i + 1:>5}  lead={leading:<3} {lines[i][:70]!r}")

# The def line is at class-method level (4 spaces).  Everything in the body must be at least
# 4 and consistently nested.  Strategy: strip ALL leading whitespace from the body, then
# re-indent from scratch using the original relative nesting derived from the previous pass:
# we know the intended body is the block as emitted by the patch script, which had a uniform
# 4-space base plus normal nesting.  So: any line whose leading < 4 gets +4, repeatedly.
fixed = []
changed = 0
for i in range(start, end):
    line = lines[i]
    if i == start:
        fixed.append(line)
        continue
    if not line.strip():
        fixed.append(line)
        continue
    leading = len(line) - len(line.lstrip(" "))
    while leading < 4:
        line = "    " + line
        leading += 4
        changed += 1
    fixed.append(line)

print(f"\nlines adjusted: {changed}")
lines = lines[:start] + fixed + lines[end:]
io.open(PATH, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("written")
