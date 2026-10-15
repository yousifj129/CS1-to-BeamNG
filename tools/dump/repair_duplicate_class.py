"""
Repair tools/beamng_convert.py after a bad splice duplicated the class.

Two faults to fix:
  1. `class BeamNGLevelBuilder` and its methods appear twice -- the second copy must go.
  2. Two module-level helpers (make_building_dae, build_material_definitions,
     BUILDING_MATERIAL_FOR_SERVICE, building_material_name) were inserted INSIDE a class, so
     they carry 4-space indentation.  They must be dedented and moved above the class.
"""

import io
import re

PATH = r"D:\Developer\open source projects\cities-skylines-to-beamng-map\tools\beamng_convert.py"

lines = io.open(PATH, encoding="utf-8").read().split("\n")
print(f"start: {len(lines)} lines")

# ---------------------------------------------------------------- 1. drop the duplicate class
class_at = [i for i, l in enumerate(lines) if l.startswith("class BeamNGLevelBuilder")]
print(f"class BeamNGLevelBuilder at lines: {[i + 1 for i in class_at]}")
if len(class_at) == 2:
    # Keep the FIRST copy; remove from the second occurrence of the class line up to EOF-level
    # duplication end.  Because the duplicate runs to the end of the class, find the first
    # module-level def after the second class that is NOT part of the class.
    second = class_at[1]
    # The duplicate block ends where the original class ended.  Find the first top-level
    # module-level construct after `second` (zip_mod is the next top-level function).
    tail = None
    for i in range(second + 1, len(lines)):
        if lines[i].startswith("def zip_mod("):
            tail = i
            break
    if tail is None:
        raise SystemExit("could not find the end of the duplicated class")
    print(f"removing duplicated class lines {second + 1}..{tail}")
    lines = lines[:second] + lines[tail:]

# ---------------------------------------------------------------- 2. dedent misplaced helpers
# They are currently 4-space indented module-level functions sitting inside the class body.
helper_names = (
    "def make_building_dae(",
    "def build_material_definitions(",
    "def building_material_name(",
)
for name in helper_names:
    hits = [i for i, l in enumerate(lines) if l.strip().startswith(name)]
    print(f"{name}: {[i + 1 for i in hits]}")

# Extract the contiguous block containing all three helpers plus the constant dict.
start = next(i for i, l in enumerate(lines) if l.strip().startswith("def make_building_dae("))
# Walk back to include comments directly above.
while start > 0 and (lines[start - 1].strip().startswith("#") or lines[start - 1].strip() == ""):
    start -= 1
end = next(i for i, l in enumerate(lines) if l.strip().startswith("def emit_terrain_materials(self)"))
# Trim trailing blanks from the extracted block.
block_end = end
while block_end > start and lines[block_end - 1].strip() == "":
    block_end -= 1
block = lines[start:block_end]
print(f"misplaced helper block: lines {start + 1}..{block_end} ({len(block)} lines)")

# Remove it from its current position.
lines = lines[:start] + lines[end:]

# Dedent one level (4 spaces) where present.
dedented = []
for line in block:
    if line.startswith("    "):
        dedented.append(line[4:])
    else:
        dedented.append(line)

# Insert immediately before the class definition.
class_line = next(i for i, l in enumerate(lines) if l.startswith("class BeamNGLevelBuilder"))
print(f"inserting helpers before class at line {class_line + 1}")
lines = lines[:class_line] + dedented + [""] + lines[class_line:]

text = "\n".join(lines)
io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)

# ---------------------------------------------------------------- verify shape
import collections

defs = collections.Counter(l for l in lines if l.startswith(("class ", "def ")))
dups = {k: v for k, v in defs.items() if v > 1}
print()
print(f"final: {len(lines)} lines")
print(f"duplicate top-level constructs: {dups if dups else 'NONE'}")
for want in ("def make_building_dae(", "def build_material_definitions(",
             "class BeamNGLevelBuilder", "def zip_mod(", "def verify_level("):
    count = sum(1 for l in lines if l.strip().startswith(want.rstrip("(") + "(" ) or l.startswith(want))
    print(f"  {want:<36} x{count}")
