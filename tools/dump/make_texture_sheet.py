"""
Decode candidate ground textures to PNG tiles so they can be LOOKED at, not just averaged.

Averaging was the mistake: `t_forest_ground_02_b` averages to (121, 124, 97) -- slightly green -- but
renders red, because its mean is dominated by large red-brown regions while the green is local
detail.  A mean cannot describe a texture's appearance.

This writes a contact sheet of the actual pixels.
"""

import io
import os
import struct
import zipfile
import zlib

GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"
OUT = r"D:\Developer\open source projects\cities-skylines-to-beamng-map\build\texture_sheet.png"

CANDIDATES = [
    ("terrain/grass/t_grass_01/t_grass_01_b.png", "grass/t_grass_01"),
    ("terrain/grass/t_grass_02/t_grass_02_b.png", "grass/t_grass_02"),
    ("terrain/grass/ind_grass/t_ind_grass_b.png", "grass/ind_grass"),
    ("terrain/grass/macro_grass/t_macro_grass_b.png", "grass/macro_grass"),
    ("terrain/forest/t_forest_ground_02/t_forest_ground_02_b.png", "forest/ground_02"),
    ("terrain/forest/t_forest_ground/t_forest_ground_b.png", "forest/ground"),
    ("terrain/forest/t_macro_forest/t_macro_forest_b.png", "forest/macro_forest"),
    ("terrain/forest/t_moss/t_moss_b.png", "forest/t_moss"),
    ("terrain/soil/t_dirt_dry_grass/t_dirt_dry_grass_b.png", "soil/dry_grass"),
    ("terrain/grass/t_dirt_vegetation/t_dirt_vegetation_b.png", "grass/dirt_veg"),
]


def decode_png(blob):
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", blob[16:24])
    ctype = blob[25]
    ch = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype)
    if ch is None:
        return None
    off, raw = 8, bytearray()
    while off < len(blob):
        ln = struct.unpack(">I", blob[off : off + 4])[0]
        tag = blob[off + 4 : off + 8]
        if tag == b"IDAT":
            raw += blob[off + 8 : off + 8 + ln]
        elif tag == b"IEND":
            break
        off += 12 + ln
    try:
        data = zlib.decompress(bytes(raw))
    except Exception:
        return None
    pitch = w * ch
    out = bytearray(h * pitch)
    prev = bytearray(pitch)
    pos = 0
    for y in range(h):
        if pos >= len(data):
            break
        ft = data[pos]
        pos += 1
        line = bytearray(data[pos : pos + pitch])
        pos += pitch
        if len(line) < pitch:
            break
        if ft == 1:
            for i in range(ch, pitch):
                line[i] = (line[i] + line[i - ch]) & 0xFF
        elif ft == 2:
            for i in range(pitch):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(pitch):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(pitch):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out[y * pitch : (y + 1) * pitch] = line
        prev = line
    return w, h, ch, bytes(out)


def write_png_rgb(path, pixels, width, height):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += pixels[y * width * 3 : (y + 1) * width * 3]

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


z = zipfile.ZipFile(os.path.join(GAME, "content", "assets", "materials", "terrain.zip"))
TILE = 256
COLS = 5
rows = (len(CANDIDATES) + COLS - 1) // COLS
sheet = bytearray(TILE * COLS * TILE * rows * 3)

for idx, (member, label) in enumerate(CANDIDATES):
    full = "assets/materials/" + member
    if full not in z.namelist():
        print("missing", member)
        continue
    got = decode_png(z.read(full))
    if not got:
        print("undecodable", member)
        continue
    w, h, ch, pix = got
    cx, cy = idx % COLS, idx // COLS
    for ty in range(TILE):
        sy = ty * h // TILE
        for tx in range(TILE):
            sx = tx * w // TILE
            o = (sy * w + sx) * ch
            if ch >= 3:
                r, g, b = pix[o], pix[o + 1], pix[o + 2]
            else:
                r = g = b = pix[o]
            d = ((cy * TILE + ty) * (TILE * COLS) + cx * TILE + tx) * 3
            sheet[d] = r
            sheet[d + 1] = g
            sheet[d + 2] = b
    print(f"row {cy} col {cx}: {label}")

z.close()
os.makedirs(os.path.dirname(OUT), exist_ok=True)
write_png_rgb(OUT, sheet, TILE * COLS, TILE * rows)
print()
print("contact sheet:", OUT, f"{TILE*COLS}x{TILE*rows}")
print("order, left to right then down:")
for i, (_m, label) in enumerate(CANDIDATES):
    print(f"   {i}: {label}")
