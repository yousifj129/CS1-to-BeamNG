"""
Find terrain texture sets whose base textures are at least 2048x2048.

The log gives the real cause of the persistent black ground:

    E|TerrainCellMaterial| Terrain material [Grass] using texture
    [.../grass/t_grass_02/t_grass_02_b.png] dont have required size of 2048-2048
    declared in TerrainMaterialTextureSet named [CannesTerrainMaterialTextureSet]

`TerrainMaterialTextureSet.baseTexSize` declares a required pixel size, and every texture in the
BASE family must match it.  It was set to [2048,2048] while the grass sets I used are 1024x1024, so
the engine rejected them and the cache packed a black layer.

Two fixes are possible: shrink `baseTexSize` to match 1024 textures, or use 2048 textures.  This
scans the install to see what is actually available at 2048 and above in each family.
"""

import os
import struct
import zipfile
from collections import defaultdict

GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"


def png_size(blob):
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", blob[16:24])


terrain = os.path.join(GAME, "content", "assets", "materials", "terrain.zip")
z = zipfile.ZipFile(terrain)

sizes = {}
for info in z.infolist():
    name = info.filename
    if not name.lower().endswith(".png"):
        continue
    try:
        head = z.read(name)[:24]
    except Exception:
        continue
    dim = png_size(head)
    if dim:
        sizes[name] = dim
z.close()

print(f"terrain.zip PNGs: {len(sizes)}")
print()

# Group by texture family directory.
families = defaultdict(list)
for name, dim in sizes.items():
    families[os.path.dirname(name)].append((os.path.basename(name), dim))

# A usable BASE set needs _b, _nm, _r, _ao, _h all at >= 2048.
def classify(folder, files):
    stem = os.path.basename(folder)
    have = {}
    for fname, dim in files:
        for suffix in ("_b", "_nm", "_r", "_ao", "_h"):
            if fname.endswith(suffix + ".png"):
                have[suffix] = dim
    return stem, have


print("=" * 96)
print("SETS WITH ALL FIVE FAMILY TEXTURES AT 2048x2048 OR LARGER")
print("=" * 96)
good = []
for folder, files in sorted(families.items()):
    stem, have = classify(folder, files)
    if len(have) == 5 and all(d[0] >= 2048 and d[1] >= 2048 for d in have.values()):
        good.append((folder, have))
        print(f"  {folder}")
        for suffix in ("_b", "_nm", "_r", "_ao", "_h"):
            print(f"       {suffix:<4} {have[suffix][0]}x{have[suffix][1]}")

print()
print(f"total usable base sets at >=2048: {len(good)}")

print()
print("=" * 96)
print("SIZE DISTRIBUTION ACROSS ALL TERRAIN SETS")
print("=" * 96)
dist = defaultdict(int)
for folder, files in families.items():
    stem, have = classify(folder, files)
    if len(have) == 5:
        dist[have["_b"]] += 1
for dim in sorted(dist):
    print(f"  {dim[0]}x{dim[1]} : {dist[dim]} sets")
