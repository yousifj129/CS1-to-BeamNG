"""
Use the user's grass texture as the terrain's base colour layer.

WHY THIS IS THE RIGHT FIX
-------------------------
Every engine terrain texture measured near-neutral grey; the greenest had a bias of +15. The supplied
`textures/grass.jpg` measures **RGB (89, 99, 45), bias +31.7** -- twice as green as anything the
engine ships, and it is actual grass rather than gravel with green flecks.

That matters because of the structure established earlier: the BASE family carries the ground's
colour, and a level normally supplies its own large colour texture for that slot. No built-in texture
can fill it. This one can.

WHAT IS WRITTEN
---------------
`textures/grass.jpg` (893x894 JPEG) becomes `levels/<level>/art/terrains/t_grass_ground_b.png`:

* converted to PNG, which is the format every terrain texture reference in this codebase uses;
* squared and resized to **1024x1024**, a power of two, because `baseTexSize` declares a required
  size and a non-matching texture is discarded -- that rule cost several rounds already.

Only the BASE COLOUR slot is replaced. Normal, roughness, ao and height stay on the engine's
`t_forest_ground_02` set, which is legitimate: those are detail maps that modulate whatever colour is
underneath, which is exactly how the engine's own materials are built.

Requested follow-up once this looks right: proper normal/roughness maps for the supplied texture.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- converter helper -------------------------------------------------------------------------
HELPER = '''

# ==========================================================================================
#  Custom terrain colour texture
# ==========================================================================================
#
# A level normally ships a large colour texture for its terrain base layer -- polish_roads_v2's is a
# 2048 m satellite photograph of its own map.  A converter has no such image, and every terrain
# texture the engine ships measures near-neutral grey (the greenest has a green bias of +15), so the
# ground could not be made green from built-in content.  This uses a supplied grass image instead.
#
# `custom_terrain_texture` is written to `levels/<level>/art/terrains/` and referenced from the
# material's `baseColorBaseTex`.  Normal, roughness, ao and height stay on the engine's set: those
# modulate whatever colour sits underneath, which is how the engine's own materials are built.
CUSTOM_TERRAIN_TEXTURE_NAME = "t_grass_ground_b.png"
CUSTOM_TERRAIN_TEXTURE_SIZE = 1024
CUSTOM_TERRAIN_TEXTURE_SOURCE = "textures/grass.jpg"


def convert_custom_terrain_texture(source_path: str, destination_path: str, size: int) -> Optional[str]:
    """
    Convert a supplied ground image into the terrain colour texture the level ships.

    Squared and resized to a power of two because `baseTexSize` declares a REQUIRED size and the
    engine discards any texture that does not match it -- a rule that cost several rounds here.
    Returns the destination path, or None if the source is missing or unreadable, so a level can
    still be built without it.
    """
    if not os.path.isfile(source_path):
        return None

    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        with Image.open(source_path) as image:
            image = image.convert("RGB")
            # Centre-crop to a square so the texture does not stretch.
            width, height = image.size
            edge = min(width, height)
            left = (width - edge) // 2
            top = (height - edge) // 2
            image = image.crop((left, top, left + edge, top + edge))
            image = image.resize((size, size), Image.LANCZOS)

            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            image.save(destination_path, format="PNG")
        return destination_path
    except Exception:
        return None

'''

anchor = "# ==========================================================================================\n#  Level builder"
if anchor not in src:
    raise SystemExit("level builder banner not found")
src = src.replace(anchor, HELPER.strip() + "\n\n\n" + anchor, 1)

# ---- emit the texture, and point the material at it -------------------------------------------
OLD = """        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)"""

NEW = """        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)

        # Ship the supplied ground colour texture in the level, and point the base colour slot at it.
        # Only that slot changes; the normal, roughness, ao and height families stay on the engine
        # set, which is how the engine's own materials are built.
        source = os.path.join(self.output_root, os.pardir, CUSTOM_TERRAIN_TEXTURE_SOURCE)
        source = os.path.normpath(source)
        converted = convert_custom_terrain_texture(
            source,
            os.path.join(terrain_dir, CUSTOM_TERRAIN_TEXTURE_NAME),
            CUSTOM_TERRAIN_TEXTURE_SIZE,
        )
        if converted:
            grass_key = next(
                (k for k, v in definitions.items()
                 if isinstance(v, dict) and v.get("internalName") == "Grass"),
                None,
            )
            if grass_key is not None:
                definitions[grass_key]["baseColorBaseTex"] = (
                    f"/levels/{self.level_name.lower()}/art/terrains/{CUSTOM_TERRAIN_TEXTURE_NAME}"
                )
            self.report["customTerrainTexture"] = CUSTOM_TERRAIN_TEXTURE_NAME
        else:
            self.report.setdefault("warnings", []).append(
                f"custom terrain texture not found or unreadable: {CUSTOM_TERRAIN_TEXTURE_SOURCE}"
            )

        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)"""

if OLD not in src:
    raise SystemExit("terrain material write anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- base tile scaled for the supplied texture -------------------------------------------------
# 1024 px over 32 m is 3.1 cm per texel: fine enough not to pixelate, coarse enough not to visibly
# repeat across a 32 km world.
import re

start = src.index("CS1_TERRAIN_MATERIAL = {")
end = src.index("\n}", start)
block = src[start:end]
for field in ("baseColorBaseTexSize", "normalBaseTexSize", "roughnessBaseTexSize",
              "aoBaseTexSize", "heightBaseTexSize"):
    block = re.sub(r'("%s":\s*)[\d.]+' % re.escape(field), lambda m: m.group(1) + "32", block, count=1)
src = src[:start] + block + src[end:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("test" if False else "  converter helper :", "def convert_custom_terrain_texture(" in src)
print("  material rewire  :", "CUSTOM_TERRAIN_TEXTURE_NAME}" in src)
print("  base tile 32 m   :", '"baseColorBaseTexSize": 32' in src)
