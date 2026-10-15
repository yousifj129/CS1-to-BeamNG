"""
Rebuild tools/beamng_convert.py deterministically from the pre-splice backup.

The backup (build/beamng_convert.py.bak) contains, in order:
  * the new template-based emit_sky_and_sun
  * a stale duplicate emit_terrain_materials (classic v1)
  * the correct v1.5 emit_terrain_materials
  * emit_terrain_materials' driver onward

Target file = [backup header .. end of emit_sky_and_sun]
            + [backup v1.5 emit_terrain_materials .. end of file]
"""

import collections
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
BACKUP = os.path.join(REPO, "build", "beamng_convert.py.bak")
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")

lines = io.open(BACKUP, encoding="utf-8").read().split("\n")


def find(predicate, start=0):
    for i in range(start, len(lines)):
        if predicate(lines[i]):
            return i
    raise SystemExit("anchor not found")


sky = find(lambda l: l.strip().startswith("def emit_sky_and_sun(self)"))
# Next top-level method after the sky block is the v1.5 terrain material.
v15 = find(lambda l: l.strip().startswith("def "), sky + 1)
# The stale duplicate follows it.
stale = find(lambda l: l.strip().startswith("def "), v15 + 1)
driver = find(lambda l: l.strip().startswith("def build(self)"), stale + 1)

assert "v1.5 (PBR)" in "\n".join(lines[v15 : v15 + 4]), "v1.5 block not found"
assert "Terrain material: a texture plus its definition" in "\n".join(
    lines[stale : stale + 4]
), "stale block not found"

print(f"header      : 1..{sky}")
print(f"sky method  : {sky + 1}..{v15}   ({v15 - sky} lines)")
print(f"v1.5 block  : {v15 + 1}..{stale}  ({stale - v15} lines)  <- kept")
print(f"stale block : {stale + 1}..{driver}  ({driver - stale} lines)  <- dropped")
print(f"driver..end : {driver + 1}..{len(lines)}")

new = lines[:v15] + lines[v15:stale] + lines[driver:]
text = "\n".join(new)

# A trailing sanity pass: exactly one of each method, and the v1.5 material present.
lines_new = text.split("\n")
defs = collections.Counter(
    l.strip() for l in lines_new if l.strip().startswith("def ") and "self" in l
)
duplicates = [k for k, v in defs.items() if v > 1]
if duplicates:
    raise SystemExit(f"duplicate methods remain: {duplicates}")
if "v1.5 (PBR)" not in text:
    raise SystemExit("v1.5 terrain material block missing")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(text)
print()
print(f"wrote {TARGET}: {len(lines_new)} lines, no duplicate methods")
