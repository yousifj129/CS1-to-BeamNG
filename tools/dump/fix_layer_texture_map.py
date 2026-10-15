"""
Write the missing `layerTextureMap` section into the .ter file.

Version 9 layout is:

    u8   version
    u32  size
    u16  heightMap[size*size]
    u8   layerMap[size*size]           which material each cell uses
    u8   layerTextureMap[size*size]    which texture layer within that material
    u32  materialCount
    ...  NUL-terminated names

The writer was emitting only four of those five sections -- the `layerTextureMap` was absent.  The
file was therefore exactly `size*size` bytes short, so the engine read the material count from past
the end of the data and resolved no materials at all.  That is the source of

    E|TerrainCellMaterial| Missing Terrain texture: /

on every slot, for every material, which is why changing the material never altered the result.
"""

import ast
import collections
import io
import os
import struct
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")

# ---- first, learn what a working v9 file stores in that section ------------------------
REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")
print("layerTextureMap contents in working v9 files:")
for archive, level in (("grille_mbwr_city.zip", "grille_mbwr_city"),
                       ("polish_roads_repo.zip", "polish_roads_v2")):
    path = os.path.join(REPO_MODS, archive)
    if not os.path.isfile(path):
        continue
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if not n.lower().endswith(".ter") or f"levels/{level}/" not in n:
                continue
            blob = z.read(n)
            version = blob[0]
            size = struct.unpack_from("<I", blob, 1)[0]
            k = size * size
            layer_off = 5 + k * 2
            tex_off = layer_off + k
            count_off = tex_off + k
            if count_off + 4 > len(blob):
                print(f"   {level}/{n.split('/')[-1]}: too short")
                continue
            layers = blob[layer_off:tex_off]
            textures = blob[tex_off:count_off]
            cnt = struct.unpack_from("<I", blob, count_off)[0]
            print(f"   {level}/{n.split('/')[-1]}  v{version} size={size} materials={cnt}")
            print(f"      layerMap        distinct={len(set(layers))} sample={list(layers[:8])}")
            print(f"      layerTextureMap distinct={len(set(textures))} sample={list(textures[:8])}")
            break

# ---- fix the writer ---------------------------------------------------------------------
src = io.open(TARGET, encoding="utf-8").read()

OLD_DOC = """        u8   version
        u32  size                          (heightmap resolution, power of two)
        u16  heightMap[size * size]
        u8   layerMap[size * size]
        u32  materialCount
        ...  materialCount NUL-terminated name strings

    The companion .terrain.json is descriptive only; this file is the terrain.
    \"\"\""""
NEW_DOC = """        u8   version
        u32  size                          (heightmap resolution, power of two)
        u16  heightMap[size * size]
        u8   layerMap[size * size]         which material each cell uses
        u8   layerTextureMap[size * size]  which texture layer within that material
        u32  materialCount
        ...  materialCount NUL-terminated name strings

    The companion .terrain.json is descriptive only; this file is the terrain.

    `layerTextureMap` was previously omitted, making the file exactly size*size bytes short.  The
    engine then read the material count past the end of the data and resolved no materials, which
    surfaced as `TerrainCellMaterial| Missing Terrain texture: /` for every slot -- and no material
    change could affect it, because the file itself was malformed.
    \"\"\""""
src = src.replace(OLD_DOC, NEW_DOC, 1)

OLD_WRITE = """    height_bytes = np.ascontiguousarray(terrain.heights, dtype="<u2").tobytes()
    layer_bytes = np.ascontiguousarray(terrain.layers, dtype=np.uint8).tobytes()

    with open(path, "wb") as handle:
        handle.write(struct.pack("<B", TERRAIN_FILE_VERSION))
        handle.write(struct.pack("<I", int(terrain.size)))
        handle.write(height_bytes)
        handle.write(layer_bytes)
        handle.write(struct.pack("<I", len(material_names)))
        for name in material_names:
            handle.write(name.encode("ascii", "replace") + b"\\x00")

    return os.path.getsize(path)"""

NEW_WRITE = """    height_bytes = np.ascontiguousarray(terrain.heights, dtype="<u2").tobytes()
    layer_bytes = np.ascontiguousarray(terrain.layers, dtype=np.uint8).tobytes()

    # Version 9 requires the layerTextureMap section between the layer map and the material count.
    # It selects which texture layer inside each material a cell uses; with one material and one
    # layer, zero for every cell is correct.
    texture_bytes = b"\\x00" * (terrain.size * terrain.size)

    with open(path, "wb") as handle:
        handle.write(struct.pack("<B", TERRAIN_FILE_VERSION))
        handle.write(struct.pack("<I", int(terrain.size)))
        handle.write(height_bytes)
        handle.write(layer_bytes)
        handle.write(texture_bytes)
        handle.write(struct.pack("<I", len(material_names)))
        for name in material_names:
            handle.write(name.encode("ascii", "replace") + b"\\x00")

    expected = 5 + terrain.size * terrain.size * 4 + 4 + sum(
        len(n) + 1 for n in material_names
    )
    actual = os.path.getsize(path)
    if actual != expected:
        raise ValueError(
            f".ter is {actual} bytes but version 9 layout requires {expected} "
            f"(difference {expected - actual})"
        )

    return actual"""
if OLD_WRITE not in src:
    raise SystemExit("writer anchor not found")
src = src.replace(OLD_WRITE, NEW_WRITE, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print()
print("SYNTAX OK")
print("layerTextureMap written :", "texture_bytes" in src)
print("size assertion added    :", "version 9 layout requires" in src)
