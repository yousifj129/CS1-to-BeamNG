"""
Extract, verbatim, a complete working TerrainMaterial from the template level, plus the
TerrainMaterialTextureSet it belongs to, so the converter can emit them unchanged.

This removes all guesswork: the template level is the engine's own starting point, so its
material is guaranteed loadable, and its textures are the ones third-party maps reference.
"""

import json
import os
import zipfile

TEMPLATE = r"D:\SteamLibrary\steamapps\common\BeamNG.drive\content\levels\template.zip"
OUT = r"D:\Developer\open source projects\cities-skylines-to-beamng-map\build\template_materials.json"

with zipfile.ZipFile(TEMPLATE) as archive:
    name = "levels/template/art/terrains/main.materials.json"
    data = json.loads(archive.read(name).decode("utf-8", "replace"))

texture_set = None
materials = {}
for key, value in data.items():
    if not isinstance(value, dict):
        continue
    if value.get("class") == "TerrainMaterialTextureSet":
        texture_set = value
    elif value.get("class") == "TerrainMaterial":
        materials[value.get("internalName")] = value

print(f"texture sets : {texture_set is not None}")
print(f"materials    : {len(materials)} -> {sorted(materials)}")
print()

# Show one material in full, and list which texture files it references.
for name in ("Grass", "Asphalt"):
    material = materials.get(name)
    if not material:
        continue
    print("=" * 100)
    print(f"TerrainMaterial '{name}'")
    print("=" * 100)
    print(json.dumps(material, indent=2))
    print()

# Which textures does the grass material need, and do they exist in the archive?
with zipfile.ZipFile(TEMPLATE) as archive:
    available = {os.path.basename(e.filename): e.file_size for e in archive.infolist()}

print("=" * 100)
print("texture availability check")
print("=" * 100)
for name in ("Grass", "Asphalt"):
    material = materials.get(name)
    if not material:
        continue
    print(f"--- {name}")
    for field, value in sorted(material.items()):
        if isinstance(value, str) and field.endswith("Tex") and "/" in value:
            base = os.path.basename(value)
            size = available.get(base)
            if size is None:
                # maybe a .link
                size = available.get(base + ".link")
                state = f"link only ({size} B)" if size else "MISSING"
            else:
                state = f"present ({size:,} B)"
            print(f"    {field:<26} {base:<38} {state}")

with open(OUT, "w", encoding="utf-8") as handle:
    json.dump({"textureSet": texture_set, "materials": materials}, handle, indent=2)
print()
print("saved to", OUT)
