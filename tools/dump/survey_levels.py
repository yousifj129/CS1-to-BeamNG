"""
Classify every installed level by terrain-material generation, and dump the exact terrain
material format for a classic (v1) level plus its TerrainBlock fields.

BeamNG has two terrain material paths:
  * v1 "classic"    -- TerrainBlock has NO materialTextureSet, materials use diffuseMap etc.
  * v1.5 PBR        -- TerrainBlock references a TerrainMaterialTextureSet, materials use
                       baseColor*/normal*/roughness* texture arrays.
Which one a level uses is decided entirely by the TerrainBlock.  Getting this wrong is why a
terrain can load but render as WARNING_MATERIAL.
"""

import json
import os
import re
import zipfile

CONTENT = r"D:\SteamLibrary\steamapps\common\BeamNG.drive\content\levels"


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


def scan_zip(path):
    """Return (terrain_block, material_sample, material_file, level_name)."""
    block = None
    material_file = None
    materials = None
    level_name = None

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            match = re.match(r"levels/([^/]+)/info\.json$", name)
            if match:
                level_name = match.group(1)
                break

        for name in names:
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

        for name in names:
            if re.search(r"art/terrains?/main\.materials\.json$", name, re.I):
                info = archive.getinfo(name)
                if info.file_size == 0 or info.file_size > 4_000_000:
                    continue
                try:
                    data = json.loads(archive.read(name).decode("utf-8", "replace"))
                except Exception:
                    continue
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, dict) and value.get("class") == "TerrainMaterial":
                            materials = (key, value)
                            material_file = name
                            break
            if materials:
                break

    return block, materials, material_file, level_name


def main():
    rows = []
    for name in sorted(os.listdir(CONTENT)):
        if not name.endswith(".zip"):
            continue
        path = os.path.join(CONTENT, name)
        try:
            block, materials, material_file, level_name = scan_zip(path)
        except Exception as exc:
            print(f"{name}: scan failed: {exc}")
            continue

        if block is None and materials is None:
            continue

        has_texture_set = bool(block.get("materialTextureSet")) if block else None
        generation = "v1.5" if has_texture_set else ("v1" if block else "?")

        diffuse = materials[1].get("diffuseMap") if materials else None
        base_color = materials[1].get("baseColorBaseTex") if materials else None

        rows.append({
            "zip": name,
            "level": level_name,
            "hasBlock": block is not None,
            "gen": generation,
            "materialFile": material_file,
            "key": materials[0] if materials else None,
            "internalName": materials[1].get("internalName") if materials else None,
            "groundmodel": materials[1].get("groundmodelName") if materials else None,
            "diffuseMap": diffuse,
            "baseColorBaseTex": base_color,
            "block": block,
            "material": materials[1] if materials else None,
        })

    print("=" * 110)
    print("terrain generation per level")
    print("=" * 110)
    print(f"{'zip':<26} {'level':<22} {'gen':<6} {'groundmodel':<14} material file")
    print("-" * 110)
    for row in rows:
        print(f"{row['zip']:<26} {str(row['level']):<22} {row['gen']:<6} "
              f"{str(row['groundmodel']):<14} {row['materialFile']}")

    classics = [r for r in rows if r["gen"] == "v1" and r["material"]]
    print()
    print("=" * 110)
    print(f"classic (v1) levels with materials: {len(classics)}")
    print("=" * 110)
    for row in classics[:3]:
        print()
        print(f"--- {row['zip']} / {row['level']}")
        print("    TerrainBlock:")
        for key, value in row["block"].items():
            print(f"      {key}: {json.dumps(value)[:100]}")
        print("    TerrainMaterial:")
        for key, value in row["material"].items():
            rendered = json.dumps(value)
            if len(rendered) > 110:
                rendered = rendered[:110] + "..."
            print(f"      {key}: {rendered}")

    v15 = [r for r in rows if r["gen"] == "v1.5" and r["material"]]
    if v15:
        row = v15[0]
        print()
        print("=" * 110)
        print(f"v1.5 example for contrast: {row['zip']} / {row['level']}")
        print("=" * 110)
        print("    TerrainBlock materialTextureSet:", row["block"].get("materialTextureSet"))
        for key, value in row["material"].items():
            rendered = json.dumps(value)
            if len(rendered) > 110:
                rendered = rendered[:110] + "..."
            print(f"      {key}: {rendered}")


if __name__ == "__main__":
    main()
