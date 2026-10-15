"""Render the exact textures the shipped grass material uses, at the tiles that are set."""

import os
import struct
import sys
import zipfile
import zlib

sys.path.insert(0, r"D:\Developer\open source projects\cities-skylines-to-beamng-map\tools\dump")
from make_texture_sheet import decode_png, write_png_rgb  # noqa: E402

GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"
OUT = r"D:\Developer\open source projects\cities-skylines-to-beamng-map\build\current_stack.png"

# The three colour textures the shipped material names, with their tile sizes in metres.
STACK = [
    ("assets/materials/terrain/forest/t_forest_ground_02/t_forest_ground_02_b.png", "BASE  forest/ground_02  4 m"),
    ("assets/materials/terrain/grass/t_grass_02/t_grass_02_b.png", "DETAIL grass/t_grass_02  0.5 m"),
    ("assets/materials/terrain/forest/t_macro_forest/t_macro_forest_b.png", "MACRO forest/macro_forest  1 m"),
]

z = zipfile.ZipFile(os.path.join(GAME, "content", "assets", "materials", "terrain.zip"))
TILE = 320
sheet = bytearray(TILE * len(STACK) * TILE * 3)
for idx, (member, label) in enumerate(STACK):
    if member not in z.namelist():
        print("missing", member)
        continue
    w, h, ch, pix = decode_png(z.read(member))
    for ty in range(TILE):
        sy = ty * h // TILE
        for tx in range(TILE):
            sx = tx * w // TILE
            o = (sy * w + sx) * ch
            r, g, b = (pix[o], pix[o + 1], pix[o + 2]) if ch >= 3 else (pix[o],) * 3
            d = (ty * (TILE * len(STACK)) + idx * TILE + tx) * 3
            sheet[d], sheet[d + 1], sheet[d + 2] = r, g, b
    print(f"{idx}: {label}  ({w}x{h})")
z.close()

write_png_rgb(OUT, sheet, TILE * len(STACK), TILE)
print()
print("written:", OUT)
