"""Teach the .ter readers about the version 9 `layerTextureMap` section."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"

OLD_DOC = "u8 version, u32 size, u16[size^2] heights, u8[size^2] layers, u32 count, names."
NEW_DOC = (
    "u8 version, u32 size, u16[size^2] heights, u8[size^2] layers, "
    "u8[size^2] layerTextureMap, u32 count, names."
)

# The offset of the material list moves by size^2 bytes now that the layer texture map is present.
OLD_OFFSET = """    layer_start = height_start + count * 2
    names_start = layer_start + count"""
NEW_OFFSET = """    layer_start = height_start + count * 2
    # Version 9 stores a layerTextureMap between the layer map and the material count, so the
    # material list starts size^2 bytes later than a version 8 reader would expect.
    texture_start = layer_start + count
    names_start = texture_start + count"""

for rel in ("tools/verify_conversion.py", "tools/beamng_convert.py"):
    path = os.path.join(REPO, rel)
    src = io.open(path, encoding="utf-8").read()
    changed = []

    if OLD_DOC in src:
        src = src.replace(OLD_DOC, NEW_DOC, 1)
        changed.append("docstring")

    if OLD_OFFSET in src:
        src = src.replace(OLD_OFFSET, NEW_OFFSET, 1)
        changed.append("offset")

    # Report the layer texture map alongside the layer map where the reader builds its result.
    if '"layers": layers,' in src and '"layerTextureMap"' not in src:
        src = src.replace(
            '"layers": layers,',
            '"layers": layers,\n        "layerTextureMap": np.frombuffer(\n'
            '            blob, dtype=np.uint8, count=count, offset=texture_start\n'
            '        ),',
            1,
        )
        changed.append("layerTextureMap exposed")

    if changed:
        io.open(path, "w", encoding="utf-8", newline="\n").write(src)
        ast.parse(src)
        print(f"  {rel}: updated {', '.join(changed)}")
    else:
        print(f"  {rel}: no matching reader found")
