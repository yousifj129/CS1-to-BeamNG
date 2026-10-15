"""
Correct the .ter writer to the real version 9 layout.

Established arithmetically against polish_roads_v2's `theTerrainrr.ter`, 12,583,231 bytes,
version 9, size 2048:

    5 + size^2*2 + size^2 + size^2 + 4 + namebytes  = 16,777,535   <- what I assumed
    actual file length                             = 12,583,231
    shortfall                                      =  4,194,304  = exactly one size^2

So version 9 stores **no** `layerTextureMap` array.  The true layout is:

    u8   version
    u32  size
    u16  heightMap[size*size]          size^2 * 2 bytes
    u8   layerMap[size*size]           size^2 bytes
    u32  materialCount
    ...  materialCount names, each u8 length prefix + UTF-8 bytes

which reconciles exactly:

    5 + 8,388,608 + 4,194,304 + 314 = 12,583,231   (314 = 4 count + 279 name chars + 31 prefixes)

The name block was verified two independent ways: `u32 count + length-prefixed names` consumes
314/314 bytes with zero leftover, while NUL-terminated names cannot be right because the block
contains **no NUL byte at all**.  The same layout reproduces on polish_roads_winter's `.ter`
(12,583,052 bytes, 11 materials).

My previous change added a `layerTextureMap` section, making the file 67 MB TOO LARGE -- a
regression I introduced while "fixing" a defect that did not exist.  This restores the correct
layout and keeps a length assertion, now against the right formula.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD_DOC = """        u8   version
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

NEW_DOC = """        u8   version
        u32  size                          (heightmap resolution, power of two)
        u16  heightMap[size * size]
        u8   layerMap[size * size]         which material each cell uses
        u32  materialCount
        ...  materialCount names, each u8 length prefix + UTF-8 bytes

    Verified arithmetically against polish_roads_v2's `theTerrainrr.ter` (12,583,231 bytes,
    version 9, size 2048):

        5 + size^2*2 + size^2 + 4 + name bytes  =  12,583,231   exactly

    There is NO `layerTextureMap` array, despite what `.terrain.json`'s `binaryFormat` string
    claims.  With one it would need 4,194,304 more bytes than the file has, so version 9 does not
    store one; the descriptive string is simply wrong.  Names are length-prefixed, not
    NUL-terminated -- the name block contains no NUL byte, and a 4-byte count plus length-prefixed
    names consumes it to the byte.
    \"\"\""""

if OLD_DOC not in src:
    raise SystemExit("docstring anchor not found")
src = src.replace(OLD_DOC, NEW_DOC, 1)

OLD_WRITE = """    # Version 9 requires the layerTextureMap section between the layer map and the material count.
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
    )"""

NEW_WRITE = """    # Names are length-prefixed, not NUL-terminated: the real name block contains no NUL byte at
    # all, and this encoding consumes it exactly.
    name_block = bytearray()
    for name in material_names:
        encoded = name.encode("utf-8")[:255]
        name_block.append(len(encoded))
        name_block += encoded

    with open(path, "wb") as handle:
        handle.write(struct.pack("<B", TERRAIN_FILE_VERSION))
        handle.write(struct.pack("<I", int(terrain.size)))
        handle.write(height_bytes)
        handle.write(layer_bytes)
        handle.write(struct.pack("<I", len(material_names)))
        handle.write(bytes(name_block))

    expected = 5 + terrain.size * terrain.size * 3 + 4 + len(name_block)"""

if OLD_WRITE not in src:
    print("warning: writer body anchor not found; inspecting")
    raise SystemExit(1)
src = src.replace(OLD_WRITE, NEW_WRITE, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("no layerTextureMap written :", "texture_bytes" not in src)
print("length-prefixed names      :", "name_block.append(len(encoded))" in src)
print("assertion formula corrected:", "terrain.size * terrain.size * 3" in src)
