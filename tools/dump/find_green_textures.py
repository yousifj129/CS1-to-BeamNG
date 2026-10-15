"""
Find every genuinely GREEN texture in the install, not just the ones assumed to be grass.

The `_b` textures in terrain.zip are greyscale detail maps.  But other textures in the install ARE
coloured -- foliage, tree, decal and atlas archives all ship real colour maps, and a level may also
have its own.  This scans them all and reports the ones that actually measure green, so the choice is
made from data rather than from a name.
"""

import os
import struct
import zipfile

GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"

ARCHIVES = [
    "content/assets/materials/terrain.zip",
    "content/assets/materials/foliage.zip",
    "content/assets/materials/tree.zip",
    "content/assets/materials/tileable.zip",
    "content/assets/materials/atlas.zip",
    "content/assets/materials/baked_props.zip",
    "content/assets/materials/trim.zip",
    "content/assets/materials/rocks.zip",
]


def png_mean(blob, stride=8):
    """Cheap mean RGB of a PNG, sampling every `stride`-th pixel."""
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    import zlib

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
    prev = bytearray(pitch)
    tot = [0, 0, 0]
    n = 0
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
        if y % stride == 0:
            for i in range(0, pitch - ch + 1, max(ch, ch * stride)):
                if ch >= 3:
                    tot[0] += line[i]
                    tot[1] += line[i + 1]
                    tot[2] += line[i + 2]
                else:
                    tot[0] += line[i]
                    tot[1] += line[i]
                    tot[2] += line[i]
                n += 1
        prev = line
    if not n:
        return None
    return tuple(t // n for t in tot)


results = []
for rel in ARCHIVES:
    path = os.path.join(GAME, *rel.split("/"))
    if not os.path.isfile(path):
        continue
    try:
        z = zipfile.ZipFile(path)
    except Exception:
        continue
    for name in z.namelist():
        low = name.lower()
        if not low.endswith(".png"):
            continue
        if any(t in low for t in ("_nm", "_r.png", "_ao", "_h.png", "_m.", "normal", "rough")):
            continue
        try:
            blob = z.read(name)
        except Exception:
            continue
        rgb = png_mean(blob)
        if rgb is None:
            continue
        green = rgb[1] - (rgb[0] + rgb[2]) / 2.0
        if green > 4.0:
            results.append((green, rgb, rel.split("/")[-1], name))
    z.close()

results.sort(reverse=True)
print(f"textures with a green bias > 4, across {len(ARCHIVES)} archives: {len(results)}")
print()
print(f"{'archive':<16}{'green':>7}  RGB                name")
print("-" * 104)
for green, rgb, archive, name in results[:40]:
    print(f"{archive:<16}{green:>7.1f}  {str(rgb):<18} {name}")
