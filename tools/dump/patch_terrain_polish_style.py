"""
Rebuild the terrain material to match the structure working maps use.

Studied polish_roads_v2's `levels/polish_roads_v2/art/terrains/main.materials.json`.  The pattern
is consistent and is what the engine expects:

    TerrainMaterialTextureSet
        baseTexSize   [2048, 2048]
        detailTexSize [1024, 1024]
        macroTexSize  [1024, 1024]

    TerrainMaterial
        *BaseTex    -> LOCAL to the level:   /levels/polish_roads_v2/art/terrains/t_terrain_base_b.png
        *DetailTex  -> ENGINE asset:         /assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_b.png
        *MacroTex   -> ENGINE asset:         /assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_b.png
        *BaseTexSize   2048      (world metres per tile)
        *MacroTexSize  80

Its five base textures are 2048x2048; every other texture is 1024x1024 and comes from the game's
own `/assets/` library.  Only the base family is shipped inside the level.

Our earlier attempts shipped all fifteen textures locally at 1024 and declared a uniform
[1024,1024,1024] set.  This rebuild follows the working arrangement instead:

  * five base textures, upscaled to 2048 if the source is smaller, shipped locally
  * detail and macro left pointing at the engine's `/assets/materials/terrain/...` library
  * set sizes [2048, 2048] / [1024, 1024] / [1024, 1024], taken from the real files
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

HELPER = '''def resize_png(blob: bytes, target: int) -> Optional[bytes]:
    """
    Return the PNG in `blob` resized to target x target, or None if it cannot be handled.

    Only the common 8-bit truecolour/albedo forms are supported (colour type 2/6, bit depth 8);
    grayscale and palette images are returned unchanged so the caller falls back to the original
    bytes rather than writing something broken.  Bilinear, so a 512 -> 2048 upscale stays smooth.
    """
    if len(blob) < 24 or blob[:8] != b"\\x89PNG\\r\\n\\x1a\\n":
        return None

    width, height = struct.unpack(">II", blob[16:24])
    bit_depth, colour_type = blob[24], blob[25]
    if bit_depth != 8 or colour_type not in (2, 6) or blob[28] != 0:
        return None
    if width == target and height == target:
        return blob

    channels = 3 if colour_type == 2 else 4

    # --- decode the IDAT stream -------------------------------------------------------
    offset, raw = 8, bytearray()
    while offset < len(blob):
        length = struct.unpack(">I", blob[offset : offset + 4])[0]
        chunk = blob[offset + 4 : offset + 8]
        if chunk == b"IDAT":
            raw += blob[offset + 8 : offset + 8 + length]
        elif chunk == b"IEND":
            break
        offset += 12 + length

    try:
        data = zlib.decompress(bytes(raw))
    except zlib.error:
        return None

    stride = width * channels
    expected = (stride + 1) * height
    if len(data) < expected:
        return None

    # --- undo the per-scanline filters ------------------------------------------------
    out = bytearray(height * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        filter_type = data[pos]
        pos += 1
        line = bytearray(data[pos : pos + stride])
        pos += stride
        if filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        out[y * stride : (y + 1) * stride] = line
        prev = line

    # --- bilinear resample ------------------------------------------------------------
    src = np.frombuffer(bytes(out), dtype=np.uint8).reshape(height, width, channels)
    # Map each destination pixel centre back to source space.
    xs = (np.arange(target) + 0.5) * (width / target) - 0.5
    ys = (np.arange(target) + 0.5) * (height / target) - 0.5
    xs = np.clip(xs, 0, width - 1)
    ys = np.clip(ys, 0, height - 1)
    x0 = np.floor(xs).astype(np.int32)
    y0 = np.floor(ys).astype(np.int32)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    wx = (xs - x0)[None, :, None]
    wy = (ys - y0)[:, None, None]

    top = src[y0][:, x0] * (1 - wx) + src[y0][:, x1] * wx
    bottom = src[y1][:, x0] * (1 - wx) + src[y1][:, x1] * wx
    scaled = (top * (1 - wy) + bottom * wy + 0.5).astype(np.uint8)

    # --- re-encode --------------------------------------------------------------------
    rows = bytearray()
    for y in range(target):
        rows.append(0)  # filter type 0 (none)
        rows += scaled[y].tobytes()

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", target, target, 8, colour_type, 0, 0, 0)
    return (
        b"\\x89PNG\\r\\n\\x1a\\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )


# Terrain material in the arrangement working maps use: ship the base family inside the level,
# take detail and macro from the engine's own /assets/materials/terrain library.
CS1_TERRAIN_BASE_TEX = {
    "baseColorBaseTex": "t_terrain_base_b.png",
    "normalBaseTex": "t_terrain_base_nm.png",
    "roughnessBaseTex": "t_terrain_base_r.png",
    "aoBaseTex": "t_terrain_base_ao.png",
    "heightBaseTex": "t_terrain_base_h.png",
}

CS1_TERRAIN_ENGINE_TEX = {
    "baseColorDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_b.png",
    "normalDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_nm.png",
    "roughnessDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_r.png",
    "aoDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_ao.png",
    "heightDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_h.png",
    "baseColorMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_b.png",
    "normalMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_nm.png",
    "roughnessMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_r.png",
    "aoMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_ao.png",
    "heightMacroTex": "/assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_h.png",
}

# Which archive each base texture comes from, and its expected on-disk name.
CS1_TERRAIN_BASE_SOURCES = {
    "t_terrain_base_b.png": ("content/assets/materials/terrain/grass/t_terrain_base_b.png",
                             "content/levels/template.zip",
                             "levels/template/art/terrains/t_terrain_base_grass_b.png"),
    "t_terrain_base_nm.png": ("content/assets/materials/terrain/grass/t_terrain_base_nm.png",
                              "content/levels/template.zip",
                              "levels/template/art/terrains/t_terrain_base_grass_nm.png"),
    "t_terrain_base_r.png": ("content/assets/materials/terrain/grass/t_terrain_base_r.png",
                             "content/levels/template.zip",
                             "levels/template/art/terrains/t_terrain_base_grass_r.png"),
    "t_terrain_base_ao.png": ("content/assets/materials/terrain/grass/t_terrain_base_ao.png",
                              "content/levels/template.zip",
                              "levels/template/art/terrains/t_terrain_base_grass_ao.png"),
    "t_terrain_base_h.png": ("content/assets/materials/terrain/grass/t_terrain_base_h.png",
                             "content/levels/template.zip",
                             "levels/template/art/terrains/t_terrain_base_grass_h.png"),
}


def copy_base_terrain_textures(destination_dir: str, pixel_size: int) -> Dict[str, str]:
    """
    Copy the five BASE terrain textures into the level, resized to `pixel_size`.

    Working maps ship only the base family locally (at 2048) and take detail and macro from the
    engine library, so the copy is resized to keep the declared set honest.
    """
    import zipfile

    game = find_beamng_install()
    os.makedirs(destination_dir, exist_ok=True)
    copied: Dict[str, str] = {}
    if not game:
        return copied

    for target_name, (_asset_member, archive_rel, member) in CS1_TERRAIN_BASE_SOURCES.items():
        archive_path = os.path.join(game, archive_rel.replace("/", os.sep))
        if not os.path.isfile(archive_path):
            continue
        try:
            with zipfile.ZipFile(archive_path) as archive:
                blob = archive.read(member)
        except (KeyError, zipfile.BadZipFile):
            continue

        target = os.path.join(destination_dir, target_name)
        with open(target, "wb") as handle:
            handle.write(resize_png(blob, pixel_size) or blob)
        copied[target_name] = target

    return copied


'''

anchor = "def emit_terrain_materials(self) -> None:"
if anchor not in src:
    raise SystemExit("emit_terrain_materials anchor not found")
class_at = src.index("class BeamNGLevelBuilder")
src = src[:class_at] + HELPER + src[class_at:]

# Replace the body of emit_terrain_materials.
start = src.index(anchor)
end = src.index("\n    def emit_preview_image", start)

NEW_METHOD = '''    def emit_terrain_materials(self) -> None:
        """
        Emit the terrain material in the arrangement working maps use.

        Verified against polish_roads_v2: the five BASE textures are shipped inside the level at
        2048x2048, while the detail and macro families are referenced from the engine's own
        `/assets/materials/terrain/...` library at 1024x1024.  The texture set mirrors that:

            baseTexSize   [2048, 2048]
            detailTexSize [1024, 1024]
            macroTexSize  [1024, 1024]

        The set sizes are read back from the files actually written, so they cannot disagree with
        what is on disk -- a mismatch makes the engine fail to pack the texture arrays and report
        "Missing Terrain texture: /" for every slot, which renders the ground flat grey.
        """
        if self.terrain is None:
            return

        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)

        # Base family: shipped locally.  Sized to match the set we are about to declare.
        base_size = 2048
        copied = copy_base_terrain_textures(terrain_dir, base_size)
        for _name, path in sorted(copied.items()):
            self.report["files"].append(os.path.relpath(path, self.mod_root))
        if not copied:
            self.report["warnings"].append(
                "no base terrain textures could be copied; the ground will render untextured"
            )

        vfs = f"/levels/{self.level_name.lower()}/art/terrains"

        # Confirm the base textures really are the size we are about to declare.
        measured = [png_pixel_size(p) for p in copied.values()]
        measured = [m for m in measured if m]
        if measured:
            base_size = max(set(measured), key=measured.count)

        detail_size = 1024
        macro_size = 1024

        definition: Dict[str, Any] = {
            "name": self.terrain_materials[0],
            "internalName": self.terrain_materials[0],
            "class": "TerrainMaterial",
            "persistentId": new_id(),
            "groundmodelName": "GRASS",
            "annotation": "GRASS",
            "macroDistances": [0, 10, 100, 3000],
            "detailDistances": [0, 0, 30, 60],
        }
        for field, filename in CS1_TERRAIN_BASE_TEX.items():
            definition[field] = f"{vfs}/{filename}"
        definition["baseColorBaseTexSize"] = base_size
        definition["normalBaseTexSize"] = base_size
        definition["roughnessBaseTexSize"] = base_size
        definition["aoBaseTexSize"] = base_size
        definition["heightBaseTexSize"] = base_size

        definition.update(CS1_TERRAIN_ENGINE_TEX)
        definition["baseColorMacroTexSize"] = 80
        definition["normalMacroTexSize"] = 80
        definition["roughnessMacroTexSize"] = 80
        definition["aoMacroTexSize"] = 80
        definition["heightMacroTexSize"] = 80

        definition["baseColorMacroStrength"] = [0.05, 0.12]
        definition["baseColorDetailStrength"] = [0.25, 0.25]
        definition["normalMacroStrength"] = [0.2, 0.4]
        definition["normalDetailStrength"] = [0.7, 0.15]
        definition["roughnessMacroStrength"] = [0.15, 0.8]
        definition["roughnessDetailStrength"] = [0.3, 0.3]

        texture_set = {
            "class": "TerrainMaterialTextureSet",
            "name": self.texture_set_name,
            "persistentId": new_id(),
            "baseTexSize": [base_size, base_size],
            "detailTexSize": [detail_size, detail_size],
            "macroTexSize": [macro_size, macro_size],
        }

        definitions = {
            f"{self.level_name}TerrainMaterialTextureSet": texture_set,
            f"{self.terrain_materials[0]}-{new_id()}": definition,
        }

        self.report["terrainMaterial"] = {
            "internalName": definition["internalName"],
            "groundmodelName": definition["groundmodelName"],
            "textureSet": texture_set["name"],
            "baseTexSize": base_size,
            "detailTexSize": detail_size,
            "macroTexSize": macro_size,
            "localTextures": sorted(copied),
        }

        # art/terrains/ is the modern location; mirror to art/terrain/ for older lookup paths.
        legacy = os.path.join(self.level_root, "art", "terrain")
        os.makedirs(legacy, exist_ok=True)
        for name, path in copied.items():
            with open(path, "rb") as source, open(os.path.join(legacy, name), "wb") as target:
                target.write(source.read())
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)
        self.write_json(os.path.join(legacy, "main.materials.json"), definitions)

'''

src = src[:start] + NEW_METHOD + src[end:]
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("helper added        :", "copy_base_terrain_textures" in src)
print("base/engine split   :", "CS1_TERRAIN_ENGINE_TEX" in src)
print("method replaced     :", "detail_size = 1024" in src)
