"""
Byte-level comparison of our .ter against a working one.

The binary layout is:

    u8   version
    u32  size
    u16  size*size   heightmap
    u8   size*size   layer map          <- which material each cell uses
    u8   size*size   layer texture map  <- added in version 9
    u32  materialCount
    NUL-terminated material names

The layer TEXTURE map is easy to write as all-zeroes and is separate from the layer map.  If it is
wrong, no material can be resolved for any cell -- consistent with an unvarying error count.
This prints the statistics of both maps for ours and for a working level.
"""

import collections
import io
import os
import struct
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")


def describe(label, blob):
    version = blob[0]
    size = struct.unpack_from("<I", blob, 1)[0]
    n = size * size
    height_off = 5
    layer_off = height_off + n * 2
    texture_off = layer_off + n
    count_off = texture_off + n

    print(f"\n{label}")
    print(f"   version          : {version}")
    print(f"   size             : {size}")
    print(f"   expected bytes   : {count_off + 4}")
    print(f"   actual bytes     : {len(blob)}")
    print(f"   length matches   : {len(blob) >= count_off + 4}")

    layers = blob[layer_off:texture_off]
    textures = blob[texture_off:count_off]

    print(f"   layer map        : min={min(layers)} max={max(layers)} distinct={len(set(layers))}")
    print(f"   layer texture map: min={min(textures)} max={max(textures)} distinct={len(set(textures))}")

    cnt = struct.unpack_from("<I", blob, count_off)[0]
    off = count_off + 4
    names = []
    for _ in range(cnt):
        try:
            end = blob.index(b"\x00", off)
        except ValueError:
            print("   material names   : TRUNCATED")
            break
        names.append(blob[off:end].decode("utf-8", "replace"))
        off = end + 1
    print(f"   materials        : {cnt} {names[:4]}")
    print(f"   trailing bytes   : {len(blob) - off}")

    # A layer texture map of all zeroes is suspicious: it means every cell points at texture slot 0.
    if len(set(textures)) == 1:
        print("   NOTE: layer texture map is a single constant value")


with zipfile.ZipFile(os.path.join(REPO, "dist", "cs1_cannes.zip")) as z:
    for n in z.namelist():
        if n.lower().endswith(".ter"):
            describe("MINE (" + n.split("/")[-1] + ")", z.read(n))

for archive, level in (("grille_mbwr_city.zip", "grille_mbwr_city"),
                       ("polish_roads_repo.zip", "polish_roads_v2")):
    path = os.path.join(REPO_MODS, archive)
    if not os.path.isfile(path):
        continue
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.lower().endswith(".ter") and f"levels/{level}/" in n:
                describe(f"REF {level} ({n.split('/')[-1]})", z.read(n))
                break
