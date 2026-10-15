"""One-off repair: remove the stale duplicate emit_terrain_materials block from the converter."""

import io
import re

PATH = r"D:\Developer\open source projects\cities-skylines-to-beamng-map\tools\beamng_convert.py"

text = io.open(PATH, encoding="utf-8").read()
lines = text.split("\n")

# Find every definition of the driver and of the duplicated method.
driver_idx = [i for i, l in enumerate(lines) if l.strip().startswith("def build(self)")]
sky_idx = [i for i, l in enumerate(lines) if l.strip().startswith("def emit_sky_and_sun(self)")]
mat_idx = [i for i, l in enumerate(lines) if l.strip().startswith("def emit_terrain_materials(self)")]

print("def build            at lines:", [i + 1 for i in driver_idx])
print("def emit_sky_and_sun at lines:", [i + 1 for i in sky_idx])
print("def emit_terrain_mat at lines:", [i + 1 for i in mat_idx])

if len(mat_idx) != 2:
    raise SystemExit("expected exactly 2 emit_terrain_materials definitions, found %d" % len(mat_idx))

# The second one is stale.  Remove from the '# ---- driver' separator immediately before it
# through to the line before 'def build'.
stale_start = mat_idx[1]
separator = None
for i in range(stale_start - 1, stale_start - 6, -1):
    if "driver" in lines[i]:
        separator = i
        break
if separator is None:
    raise SystemExit("could not find the driver separator above the stale block")

end = driver_idx[0]
print(f"removing lines {separator + 1}..{end} (stale duplicate + its separator)")

new_lines = lines[:separator] + lines[end:]
io.open(PATH, "w", encoding="utf-8", newline="\n").write("\n".join(new_lines))

print("done; new line count:", len(new_lines))
