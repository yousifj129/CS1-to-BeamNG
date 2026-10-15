"""Add checks for terrain smoothness, fog, and tile scale."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

BLOCK = '''# ---------------------------------------------------------------- terrain smoothness
# Steep facets come from `_fill_gaps` interpolating across the sparse gaps between road samples, so
# the mean neighbour step is the measure that matters.  A small mean with a huge maximum means one
# isolated cliff, which is worth surfacing rather than hiding.
if ter:
    raw_ter = z.read(ter[0])
    ter_size = struct.unpack_from("<I", raw_ter, 1)[0]
    cell_count = ter_size * ter_size
    import numpy as _np
    heights = _np.frombuffer(raw_ter[5 : 5 + cell_count * 2], dtype="<u2").astype(_np.int32)
    steps = _np.abs(_np.diff(heights))
    mean_step = float(steps.mean())
    p99 = float(_np.percentile(steps, 99))
    check(mean_step < 8.0, "terrain is smooth (mean neighbour step < 8)",
          f"mean={mean_step:.2f} p99={p99:.0f} max={int(steps.max())}")

# ---------------------------------------------------------------- fog / atmosphere
for n in items:
    if "sky_and_sun" not in n:
        continue
    for obj in read_items(n):
        if obj.get("class") != "LevelInfo":
            continue
        # The template level's fog is far denser and more tinted than a working map's, which washes
        # the whole scene toward pale blue.
        density = obj.get("fogDensity")
        colour = obj.get("fogColor") or []
        check(isinstance(density, (int, float)) and density <= 0.0005,
              "fog is not denser than a working map", f"fogDensity={density}")
        check(bool(colour) and max(colour[:3]) - min(colour[:3]) < 0.05,
              "fog colour is neutral, not tinted", f"fogColor={colour[:3]}")

# ---------------------------------------------------------------- tile scale
if mat:
    base_tile = mat.get("baseColorBaseTexSize")
    check(isinstance(base_tile, (int, float)) and base_tile <= 4.0,
          "base tile is fine enough to not read as pixelated (<= 4 m)",
          f"baseColorBaseTexSize={base_tile}")

'''

anchor = "# ---------------------------------------------------------------- lighting"
if anchor not in src:
    raise SystemExit("lighting anchor not found")
src = src.replace(anchor, BLOCK + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("added smoothness/fog/tile checks; syntax OK")
