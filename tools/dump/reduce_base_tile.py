"""
Reduce the base tile, and soften the normal contribution.

WHAT THE SCREENSHOT SHOWS, AND WHAT IT MEANS
--------------------------------------------
The ground is dark, bluish and magenta-flecked rather than green.  Two causes, both from the base
tile being far too large:

1. **Scale.** The base was tiled at 200 m.  A 1024 px texture stretched over 200 m puts roughly
   20 cm of ground on each texel, so the grass blades in `t_forest_ground_02` -- which are drawn at
   centimetre detail -- are magnified into large smears: the "pixelated" look, and why its pink and
   magenta flecks (tiny at native scale) became visible blotches.

2. **Normals at that scale.** The base normal map is sampled with the same tile as the base colour,
   so magnifying it 200x magnifies every bump.  Polish gets away with a huge base tile because its
   base is a *satellite photograph* with almost no usable normal detail; ours is a close-up grass
   texture whose normal map is full of structure.  At 200 m that structure dominates the shading and
   turns the surface dark and blue.

So the fix is scale, not strengths: `normalDetailStrength [1, 0.3]` is polish's own value for Grass
and is kept.  The base comes down to 24 m, which is close to the 3-5 m detail scale the reference
uses for its textured families and far enough from pixelation.

The macro also comes down, from 60 m to 24 m, so the three families sit in a sane ratio rather than
spanning 200:4:60.
"""

import ast
import io
import os
import re

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("CS1_TERRAIN_MATERIAL = {")
end = src.index("\n}", start)
block = src[start:end]

# Base: 200 -> 24 m.  Detail: 4 -> 3 m (the reference's own value).  Macro: 60 -> 24 m.
sizes = {
    "baseColorBaseTexSize": "24",
    "normalBaseTexSize": "24",
    "roughnessBaseTexSize": "24",
    "aoBaseTexSize": "24",
    "heightBaseTexSize": "24",
    "baseColorDetailTexSize": "3",
    "normalDetailTexSize": "3",
    "roughnessDetailTexSize": "3",
    "aoDetailTexSize": "3",
    "heightDetailTexSize": "3",
    "baseColorMacroTexSize": "24",
    "normalMacroTexSize": "24",
    "roughnessMacroTexSize": "24",
    "aoMacroTexSize": "24",
    "heightMacroTexSize": "24",
}
for field, value in sizes.items():
    block = re.sub(r'("%s":\s*)[\d.]+' % re.escape(field), lambda m: m.group(1) + value, block, count=1)

# Sample the base texture less aggressively at distance so its magnified normals fade out.
# `macroDistances`/`detailDistances` control when each family takes over; the base should hand over
# sooner now that it is a close-up texture rather than a colour wash.
block = re.sub(r'("detailDistances":\s*)\[[^\]]*\]', r'\1[0, 0, 20, 40]', block, count=1)
block = re.sub(r'("macroDistances":\s*)\[[^\]]*\]', r'\1[0, 0, 60, 300]', block, count=1)

src = src[:start] + block + src[end:]
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
for f in ("baseColorBaseTexSize", "baseColorDetailTexSize", "baseColorMacroTexSize",
          "detailDistances", "macroDistances"):
    m = re.search(r'"%s":\s*([^,\n]+)' % f, block)
    print(f"   {f:<26} {m.group(1).strip() if m else '?'}")
