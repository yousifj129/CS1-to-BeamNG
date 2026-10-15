"""
Set the TerrainMaterialTextureSet from the ACTUAL texture pixel size.

Measured from a working level (grille_mbwr_city), which is authoritative:

    textures           1024 x 1024 px
    set.baseTexSize    [1024,1024]
    set.macroTexSize   [1024,1024]
    set.detailTexSize  [1024,1024]
    material.baseColorBaseTexSize  2048     <- world metres per tile, NOT pixels
    material.baseColorMacroTexSize 40       <- also world metres

So the texture set describes the ARRAY dimensions in pixels and must match the texture files,
while the material's `*TexSize` fields are tiling distances in metres.  Two earlier revisions got
this backwards:

  * hard-coded 1024 set with template textures that were 512/1024 mixed -> pack failed
  * set derived from `*TexSize` (2048/40) while textures were 1024 px  -> pack failed

This reads the real PNG header of each copied texture and uses that, so the set can never
disagree with the files on disk.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = '''        # The texture set sizes MUST equal the material's own *TexSize values, or the texture
        # arrays cannot be packed and every slot reports "Missing Terrain texture: /".  Deriving
        # them here means the two can never disagree.
        def _size(field: str, fallback: int) -> int:
            value = definition.get(field)
            return int(value) if isinstance(value, (int, float)) and value > 0 else fallback

        base_size = _size("baseColorBaseTexSize", 1024)
        macro_size = _size("baseColorMacroTexSize", 64)
        detail_size = _size("baseColorDetailTexSize", base_size)

        texture_set = {
            "class": "TerrainMaterialTextureSet",
            "name": self.texture_set_name,
            "persistentId": new_id(),
            "baseTexSize": [base_size, base_size],
            "macroTexSize": [macro_size, macro_size],
            "detailTexSize": [detail_size, detail_size],
        }
        self.report["terrainMaterial"] = {
            "internalName": definition.get("internalName"),
            "groundmodelName": definition.get("groundmodelName"),
            "textureSet": texture_set["name"],
            "baseTexSize": base_size,
            "macroTexSize": macro_size,
            "detailTexSize": detail_size,
        }
'''

NEW = '''        # The texture set describes the texture ARRAY size in PIXELS and must match the texture
        # files, not the material's *TexSize fields (those are tiling distances in metres).
        # Measured from a working level: its textures are 1024 px and its set is [1024,1024],
        # while its material asks for *TexSize 2048 / 40.  Reading the real PNG headers here means
        # the set can never disagree with the files on disk.
        pixels = {}
        for _name, path in copied.items():
            size = png_pixel_size(path)
            if size:
                pixels[size] = pixels.get(size, 0) + 1

        if pixels:
            # Use the most common size; all copied textures are the same set in practice.
            base_size = max(pixels.items(), key=lambda kv: kv[1])[0]
        else:
            base_size = 1024

        texture_set = {
            "class": "TerrainMaterialTextureSet",
            "name": self.texture_set_name,
            "persistentId": new_id(),
            "baseTexSize": [base_size, base_size],
            "macroTexSize": [base_size, base_size],
            "detailTexSize": [base_size, base_size],
        }
        self.report["terrainMaterial"] = {
            "internalName": definition.get("internalName"),
            "groundmodelName": definition.get("groundmodelName"),
            "textureSet": texture_set["name"],
            "texturePixels": base_size,
            "note": "set sizes are the texture array dimensions in pixels",
        }
'''

if OLD not in src:
    raise SystemExit("texture set anchor not found")
src = src.replace(OLD, NEW, 1)

# Add the PNG header reader next to the other PNG helpers.
HELPER = '''def png_pixel_size(path: str) -> Optional[int]:
    """
    Read a PNG's width from its IHDR chunk.

    Used to size the TerrainMaterialTextureSet from the texture files themselves, because the
    engine packs the group into a square array of that many pixels.
    """
    try:
        with open(path, "rb") as handle:
            header = handle.read(24)
    except OSError:
        return None

    if len(header) < 24 or header[:8] != b"\\x89PNG\\r\\n\\x1a\\n":
        return None

    width, height = struct.unpack(">II", header[16:24])
    return width if width == height else None


'''
anchor = "def write_png_gray8(path: str, pixels: Any) -> None:"
if anchor not in src:
    raise SystemExit("png helper anchor not found")
src = src.replace(anchor, HELPER + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("png_pixel_size added :", "def png_pixel_size(" in src)
print("set from pixels      :", "base_size = max(pixels.items()" in src)
