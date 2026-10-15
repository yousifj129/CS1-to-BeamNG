"""
Apply the measured shape centre offsets when placing buildings.

Every shape's mesh origin is a CORNER of its bounding box, not its centre:

    ind_bld_8x8    centre [-4.00, 4.00, 0.83]   (footprint 8.2 x 8.2)
    ind_bld_12x30  centre [-15.00, 5.96, 1.84]  (footprint 30.22 x 12.3)
    ind_bld_24x60  centre [0.00, -3.35, 5.57]   (footprint 60.6 x 31.3)

So placing the TSStatic at the building's centre puts the mesh half a width to one side -- up to 30 m
for the largest shape.  `__file__`-style coincidence is what made this hard to see: the collision
sits exactly where the drawn mesh is, so a car hits what it can see, but the drawn building is not
where the CS1 building was, and neighbouring buildings end up interpenetrating.

The offset is added to the placement position so the MESH's centre lands on the building's centre.

A caveat, recorded rather than hidden: `city_block3` measures 6.3x the size its table entry claims
(624.91 against 99.34), which means its geometry carries node transforms this measurement does not
apply.  Its offset is therefore not trustworthy, so shapes whose measured size disagrees with the
table by more than 20% are SKIPPED -- they keep the old centred-origin assumption rather than being
moved by a number known to be wrong.
"""

import ast
import io
import os
import re
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"

src = io.open(TARGET, encoding="utf-8").read()

# ---- measure, and keep only shapes whose size agrees with the table ---------------------------
table = {}
for m in re.finditer(
    r'\("([^"]+\.dae)",\s*"([^"]+)",\s*\(([\d.]+),\s*([\d.]+),\s*([\d.]+)\)\)', src
):
    table[m.group(1)] = (float(m.group(3)), float(m.group(4)), float(m.group(5)))


def nums(text):
    return [float(v) for v in text.split()]


measured = {}
for name, claimed in table.items():
    archive = "italy.zip" if "italy" in name or name.startswith("ind_") else "west_coast_usa.zip"
    path = os.path.join(GAME, "content", "levels", archive)
    if not os.path.isfile(path):
        continue
    with zipfile.ZipFile(path) as z:
        member = next((n for n in z.namelist() if n.endswith("/" + name)), None)
        if member is None:
            continue
        text = z.read(member).decode("utf-8", "replace")

    lo = [1e18] * 3
    hi = [-1e18] * 3
    for _gid, body in re.findall(r'<geometry[^>]*id="([^"]+)"[^>]*>(.*?)</geometry>', text, re.S):
        srcs = re.findall(r"<source[^>]*>(.*?)</source>", body, re.S)
        chosen = next((s for s in srcs if "position" in s.lower()), None)
        if chosen is None:
            best = None
            for s in srcs:
                arr = re.search(r"<float_array[^>]*>(.*?)</float_array>", s, re.S)
                if not arr:
                    continue
                vals = nums(arr.group(1))
                if best is None or len(vals) > len(best):
                    best = vals
            if best is None:
                continue
            values = best
        else:
            arr = re.search(r"<float_array[^>]*>(.*?)</float_array>", chosen, re.S)
            if not arr:
                continue
            values = nums(arr.group(1))
        if len(values) < 3:
            continue
        for axis in range(3):
            col = values[axis::3]
            lo[axis] = min(lo[axis], min(col))
            hi[axis] = max(hi[axis], max(col))

    size = [hi[i] - lo[i] for i in range(3)]
    centre = [(hi[i] + lo[i]) * 0.5 for i in range(3)]

    ratios = [size[i] / claimed[i] for i in range(3) if claimed[i] > 0]
    trustworthy = all(0.8 <= r <= 1.25 for r in ratios)
    measured[name] = (centre, size, trustworthy)
    flag = "ok " if trustworthy else "SKIP"
    print(f"  {flag} {name:<26} centre {[round(c,2) for c in centre]}  size {[round(s,2) for s in size]}")

# ---- bake the trustworthy offsets -------------------------------------------------------------
lines = [
    "",
    "# Ground-plane centre offset of each shape's mesh, in the shape's own x/z, measured from its",
    "# Collada POSITION accessors.  The mesh origin is a CORNER of the bounding box, not its centre:",
    "# ind_bld_8x8 spans 8.2 m in -X and 0.1 m in +X from its origin.  Placing the TSStatic at the",
    "# building's centre would therefore offset the whole mesh by half its width -- up to 30 m for",
    "# ind_bld_24x60 -- which is why buildings interpenetrated and sat where they should not.",
    "# Shapes whose measured size disagrees with the table by more than ~20% are omitted: their",
    "# geometry carries node transforms this measurement does not apply (e.g. city_block3, which",
    "# measures 6.3x its claimed size), so no offset is safer than a wrong one.",
    "BEAMNG_SHAPE_CENTRE_OFFSET = {",
]
for name, (centre, _size, ok) in sorted(measured.items()):
    if ok:
        lines.append(f'    "{name}": ({centre[0]:.3f}, {centre[2]:.3f}),')
lines.append("}")
block = "\n".join(lines)

# Remove any previous version of this table.
src = re.sub(
    r"\n*# Ground-plane centre offset.*?\nBEAMNG_SHAPE_CENTRE_OFFSET = \{.*?\n\}\n",
    "\n",
    src,
    flags=re.S,
)
anchor = "BEAMNG_BUILDING_MODELS = "
if anchor not in src:
    raise SystemExit("models anchor not found")
src = src.replace(anchor, block.strip() + "\n\n" + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print()
print("SYNTAX OK")
print("offsets kept:", sum(1 for v in measured.values() if v[2]), "of", len(measured))
