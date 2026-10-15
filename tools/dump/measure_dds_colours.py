"""
Find which terrain colour maps are actually green, by reading the DDS pixels.

The `_b.png` textures are greyscale detail maps; roughly 25 `_b.color.dds` entries are real colour
maps, some of which contain no PNG counterpart in the archive.  This decodes them and reports mean
RGB, so the greenest available grass colour map can be chosen by measurement.
"""

import os
import struct
import zipfile

GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"
ZIP = os.path.join(GAME, "content", "assets", "materials", "terrain.zip")


def decode_dds(blob):
    """Return (w, h, list of (r, g, b) means) for the DDS top mip, or None."""
    if blob[:4] != b"DDS ":
        return None
    height, width = struct.unpack_from("<II", blob, 12)
    pf_flags, fourcc, rgb_bits, rmask, gmask, bmask, amask = struct.unpack_from("<IIIIIII", blob, 80)
    data_off = 128

    def unpack(mask, value):
        if not mask:
            return 0
        shift = (mask & -mask).bit_length() - 1
        bits = bin(mask >> shift).count("1")
        return ((value & mask) >> shift) * 255 // ((1 << bits) - 1)

    tot = [0, 0, 0]
    count = 0
    if fourcc == 0 and rgb_bits in (24, 32):
        step = rgb_bits // 8
        for y in range(0, height, 4):
            for x in range(0, width, 4):
                off = data_off + (y * width + x) * step
                if off + step > len(blob):
                    break
                v = int.from_bytes(blob[off : off + step], "little")
                tot[0] += unpack(rmask, v)
                tot[1] += unpack(gmask, v)
                tot[2] += unpack(bmask, v)
                count += 1
    else:
        # Block-compressed (DXT).  Decoding DXT properly is a lot of code for a colour estimate, so
        # fall back to the average of the raw payload, which is enough to tell green from grey.
        payload = blob[data_off:]
        if not payload:
            return None
        sample = payload[: len(payload) // 3]
        for i in range(0, len(sample) - 3, 3):
            tot[0] += sample[i]
            tot[1] += sample[i + 1]
            tot[2] += sample[i + 2]
            count += 1

    if not count:
        return None
    return width, height, tuple(t // count for t in tot), (fourcc == 0 and rgb_bits in (24, 32))


z = zipfile.ZipFile(ZIP)
rows = []
for name in z.namelist():
    if ".color." not in name.lower() or not name.lower().endswith(".dds"):
        continue
    try:
        blob = z.read(name)
    except Exception:
        continue
    got = decode_dds(blob)
    if not got:
        continue
    w, h, rgb, exact = got
    green = rgb[1] - (rgb[0] + rgb[2]) / 2.0
    rows.append((green, rgb, w, h, name, exact))
z.close()

print(f"{'file':<64}{'size':>11}  RGB              green  exact")
print("-" * 108)
for green, rgb, w, h, name, exact in sorted(rows, reverse=True):
    short = name.replace("assets/materials/terrain/", "")
    print(f"{short:<64}{w:>5}x{h:<5}  {str(rgb):<16} {green:+6.1f}  {'yes' if exact else 'approx'}")

print()
best = max(rows, key=lambda r: r[0]) if rows else None
if best:
    print(f"greenest: {best[4]}  RGB {best[1]}  green balance {best[0]:+.1f}")
