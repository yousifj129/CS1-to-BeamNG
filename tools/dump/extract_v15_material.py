"""
Extract, verbatim, everything needed to emit a working v1.5 terrain material:
  * the full v1.5 TerrainMaterial that a modern level actually uses (whose textures are the
    shared template set, and which is therefore the right thing to copy)
  * the TerrainBlock fields for that level
  * the template texture set's file list, to confirm every referenced texture exists
"""

import json
import os
import re
import zipfile

LEVELS = r"D:\SteamLibrary\steamapps\common\BeamNG.drive\content\levels"


def objects_from(text):
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return
        try:
            obj, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            return
        yield obj


def read_level(path):
    block = None
    materials = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.endswith("items.level.json"):
                info = archive.getinfo(name)
                if info.file_size == 0 or info.file_size > 8_000_000:
                    continue
                try:
                    text = archive.read(name).decode("utf-8", "replace")
                except Exception:
                    continue
                for obj in objects_from(text):
                    if isinstance(obj, dict) and obj.get("class") == "TerrainBlock":
                        block = obj
                        break
            if block:
                break

        for name in archive.namelist():
            if re.search(r"art/terrains?/main\.materials\.json$", name, re.I):
                info = archive.getinfo(name)
                if info.file_size == 0:
                    continue
                try:
                    data = json.loads(archive.read(name).decode("utf-8", "replace"))
                except Exception:
                    continue
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, dict) and value.get("class") == "TerrainMaterial":
                            materials.append((key, value))
    return block, materials


# ---- 1. find a v1.5 material whose textures live in the shared template -----------------
print("=" * 100)
print("v1.5 TerrainMaterials whose textures are all under levels/template/")
print("=" * 100)

chosen = None
for name in sorted(os.listdir(LEVELS)):
    if not name.endswith(".zip"):
        continue
    try:
        block, materials = read_level(os.path.join(LEVELS, name))
    except Exception:
        continue
    if not block or not block.get("materialTextureSet"):
        continue
    for key, material in materials:
        texture_fields = {
            k: v for k, v in material.items()
            if isinstance(v, str) and ("Tex" in k) and v.lower().endswith((".png", ".dds"))
        }
        if texture_fields and all("/levels/template/" in v.lower() for v in texture_fields.values()):
            chosen = (name, block, key, material, texture_fields)
            break
    if chosen:
        break

if chosen:
    name, block, key, material, texture_fields = chosen
    print(f"source level : {name}")
    print(f"block        : materialTextureSet={block.get('materialTextureSet')} "
          f"squareSize={block.get('squareSize')} maxHeight={block.get('maxHeight')}")
    print(f"material key : {key}")
    print()
    print("full material definition:")
    print(json.dumps(material, indent=2))
    print()
    print("textures referenced:")
    for field, value in sorted(texture_fields.items()):
        print(f"   {field} = {value}")
else:
    print("none found; falling back to listing any v1.5 material")
    for name in sorted(os.listdir(LEVELS)):
        if name.endswith(".zip"):
            continue
    # print one from Cliff for reference
    block, materials = read_level(os.path.join(LEVELS, "Cliff.zip"))
    print("Cliff materialTextureSet:", block.get("materialTextureSet"))
    if materials:
        print(json.dumps(materials[0][1], indent=2))

# ---- 2. the template texture set, to confirm sizes ------------------------------------
print()
print("=" * 100)
print("template.zip terrain textures (name -> bytes), to check the 512/1024 size split")
print("=" * 100)
with zipfile.ZipFile(os.path.join(LEVELS, "template.zip")) as archive:
    for entry in sorted(archive.infolist(), key=lambda e: e.filename):
        if "art/terrains/" in entry.filename and entry.filename.endswith((".png", ".dds")):
            base = os.path.basename(entry.filename)
            if base.startswith(("t_terrain", "t_macro", "Macro")):
                print(f"   {base:<44} {entry.file_size:>10,}")
