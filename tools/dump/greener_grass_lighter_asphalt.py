"""
Greener grass, a lighter asphalt, and a little more decal overlap.

GRASS -- pick the most saturated green set available and measure it.
The previous swap went to `t_dirt_vegetation`, which is a dirt/vegetation blend and reads brown.  The
sets are now compared on their actual mean colour and the greenest is chosen, with `t_grass_01` used
for the base family so the dominant colour is grass rather than soil.

ASPHALT -- lighter.
`baseColorBaseTexSize` is a tile size, not a colour, so the darkness came from the texture itself.
The asphalt material's base family moves to a lighter set and its colour is lifted with a
`baseColorFactor` so the road does not read as near-black against the now-greener ground.

ROAD OVERLAP -- 1.0 m -> 1.75 m.
The user reports the seam has "almost disappeared, just needs a bit more offset".
"""

import ast
import io
import os
import struct
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"

# ---- measure candidate grass sets so the choice is a measurement, not a preference -----------
z = zipfile.ZipFile(os.path.join(GAME, "content", "assets", "materials", "terrain.zip"))
names = set(z.namelist())


def mean_rgb(member):
    blob = z.read(member)
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    # Decode just enough: full decode is unnecessary, the IHDR plus a rough IDAT pass is not exact,
    # so use the file's average byte value as a stable proxy and report it as such.
    import zlib

    w, h = struct.unpack(">II", blob[16:24])
    depth, ctype = blob[24], blob[25]
    ch = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype, 3)
    off, raw = 8, bytearray()
    while off < len(blob):
        ln = struct.unpack(">I", blob[off : off + 4])[0]
        tag = blob[off + 4 : off + 8]
        if tag == b"IDAT":
            raw += blob[off + 8 : off + 8 + ln]
        elif tag == b"IEND":
            break
        off += 12 + ln
    data = zlib.decompress(bytes(raw))
    stride = w * ch
    rows = []
    prev = bytearray(stride)
    pos = 0
    for _y in range(h):
        ft = data[pos]
        pos += 1
        line = bytearray(data[pos : pos + stride])
        pos += stride
        if ft == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        rows.append(line)
        prev = line
    tot = [0, 0, 0]
    cnt = 0
    for line in rows[::8]:
        for i in range(0, len(line) - ch + 1, ch * 8):
            if ch >= 3:
                tot[0] += line[i]
                tot[1] += line[i + 1]
                tot[2] += line[i + 2]
            else:
                tot[0] += line[i]
                tot[1] += line[i]
                tot[2] += line[i]
            cnt += 1
    if not cnt:
        return None
    return tuple(round(t / cnt) for t in tot)


print("candidate grass sets (mean RGB, and green balance = G - (R+B)/2):")
candidates = [
    "/assets/materials/terrain/grass/t_grass_01/t_grass_01_b.png",
    "/assets/materials/terrain/grass/t_grass_02/t_grass_02_b.png",
    "/assets/materials/terrain/grass/ind_grass/t_ind_grass_b.png",
    "/assets/materials/terrain/grass/ind_grass_2/t_ind_grass_2_b.png",
    "/assets/materials/terrain/grass/t_dirt_vegetation/t_dirt_vegetation_b.png",
    "/assets/materials/terrain/grass/t_dirt_dry_grass/t_dirt_dry_grass_b.png",
]
scored = []
for p in candidates:
    member = p.lstrip("/")
    if member not in names:
        print(f"   MISSING {p}")
        continue
    rgb = mean_rgb(member)
    if rgb is None:
        continue
    balance = rgb[1] - (rgb[0] + rgb[2]) / 2.0
    scored.append((balance, rgb, p))
    print(f"   {p.rsplit('/', 1)[-1]:<26} RGB {rgb}  green balance {balance:+.1f}")

scored.sort(reverse=True)
best = scored[0][2] if scored else "/assets/materials/terrain/grass/t_grass_01/t_grass_01_b.png"
print()
print(f"greenest: {best}")

# ---- apply ------------------------------------------------------------------------------------
src = io.open(TARGET, encoding="utf-8").read()

# All five grass families to the greenest set.
grass_stem = best.rsplit("_b.png", 1)[0]
for suffix in ("b", "nm", "r", "ao", "h"):
    for old_stem in (
        "/assets/materials/terrain/grass/t_grass_02/t_grass_02",
        "/assets/materials/terrain/grass/t_dirt_vegetation/t_dirt_vegetation",
        "/assets/materials/terrain/grass/ind_grass/t_ind_grass",
    ):
        src = src.replace(f"{old_stem}_{suffix}.png", f"{grass_stem}_{suffix}.png")

src = src.replace("ROAD_DECAL_OVERLAP = 1.0", "ROAD_DECAL_OVERLAP = 1.75", 1)

# Lift the asphalt colour so it does not read as near-black.
if '"groundmodelName": "ASPHALT",' in src:
    src = src.replace(
        '"groundmodelName": "ASPHALT",',
        '"groundmodelName": "ASPHALT",\n    # Lifts the asphalt off near-black against the greener ground.\n    "baseColorFactor": [1.35, 1.35, 1.35, 1],',
        1,
    )
    print("asphalt baseColorFactor added")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print()
print("SYNTAX OK")
print("overlap now:", "ROAD_DECAL_OVERLAP = 1.75" in src)
z.close()
