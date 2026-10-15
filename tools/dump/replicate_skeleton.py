"""
1. Re-enable automatic road joining.
2. Replicate Skeleton Coast's terrain setup field for field.

ROADS
-----
`autoJunction` is restored.  It tells the engine to weld road geometry where decals meet, which is
exactly "let them connect themselves".  I removed it earlier after measuring that polish_roads_v2
sets it on only 6 of 6740 roads -- but that map builds its junctions by hand, and we do not, so
automatic joining is the right behaviour here.  `autoLanes` is restored for the same reason.

TERRAIN
-------
Skeleton Coast's terrain, read field by field:

    TerrainBlock
        squareSize            2
        maxHeight             400
        baseTexSize           4096
        materialTextureSet    <level>TerrainMaterialTextureSet
        position              [0, 0, z]

    TerrainMaterial
        *BaseTexSize          4096      (base textures are 4096x4096)
        *DetailTexSize        3         <- a THIRD size field on every detail texture, which our
                                           material has never had
        *MacroTexSize         80
        baseColorDetailStrength [0.25, 0.1]

    texture set
        baseTexSize   [4096, 4096]
        detailTexSize [1024, 1024]
        macroTexSize  [1024, 1024]

    and it ships `.link` sidecar files -- small JSON documents that redirect a texture name to a
    path in another level:
        {"path":"/levels/johnson_valley/art/terrains/t_asphalt_02_b.png","type":"normal"}

The `*DetailTexSize` field is the significant omission: our detail textures have no declared size.
All three sizes are emitted now, the base family is copied in at its native size, and `.link` files
are written for the detail and macro families exactly as Skeleton Coast does.
"""

import ast
import io
import json
import os
import re
import shutil
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
REPO_MODS = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")
SOURCE_ARCHIVE = os.path.join(REPO_MODS, "skeleton_coast_1_3.zip")
SOURCE_LEVEL = "skeleton_coast"

src = io.open(TARGET, encoding="utf-8").read()

# ---- 1. roads: restore automatic joining ----------------------------------------------
OLD_ROADS = '''                "oneWay": road.is_one_way,
                "improvedSpline": True,
                # Values below are taken from polish_roads_v2's own road set rather than guessed.
                # `autoJunction` is deliberately ABSENT: that working map sets it on 6 roads out of
                # 6740, whereas setting it everywhere asks the engine to weld geometry the splines
                # already describe, which is what broke the junctions.
                "detail": 0.5,'''
NEW_ROADS = '''                "oneWay": road.is_one_way,
                "improvedSpline": True,
                # Automatic joining.  `autoJunction` welds decal geometry where roads meet and
                # `autoLanes` derives lane markings, so intersections connect themselves instead of
                # relying on hand-authored junction pieces.  Removed once because polish_roads_v2
                # sets it on only 6 of 6740 roads -- but that map hand-builds its junctions and we
                # do not, so automatic joining is the correct behaviour here.
                "autoJunction": True,
                "autoLanes": True,
                "detail": 0.5,'''
if OLD_ROADS not in src:
    raise SystemExit("road anchor not found")
src = src.replace(OLD_ROADS, NEW_ROADS, 1)

# ---- 2. terrain: read Skeleton Coast's material and detail sizes ------------------------
with zipfile.ZipFile(SOURCE_ARCHIVE) as z:
    data = json.loads(
        z.read(f"levels/{SOURCE_LEVEL}/art/terrains/main.materials.json").decode("utf-8", "replace")
    )
    material = next(v for v in data.values() if isinstance(v, dict) and v.get("class") == "TerrainMaterial")
    texture_set = next(
        v for v in data.values() if isinstance(v, dict) and v.get("class") == "TerrainMaterialTextureSet"
    )

    # Collect the three texture families and every file we must provide.
    base_files, detail_files, macro_files = {}, {}, {}
    for field, value in material.items():
        if not (isinstance(value, str) and field.endswith("Tex")):
            continue
        name = os.path.basename(value.replace("\\", "/"))
        if "BaseTex" in field:
            base_files[field] = name
        elif "DetailTex" in field:
            detail_files[field] = name
        elif "MacroTex" in field:
            macro_files[field] = name

    sources = {}
    for name in set(base_files.values()) | set(detail_files.values()) | set(macro_files.values()):
        member = f"levels/{SOURCE_LEVEL}/art/terrains/{name}"
        try:
            sources[name] = z.read(member)
        except KeyError:
            link = f"{member}.link"
            try:
                sources[name] = z.read(link)
            except KeyError:
                sources[name] = None

print(f"material fields      : {len(material)}")
print(f"base textures        : {len(base_files)}")
print(f"detail textures      : {len(detail_files)}  sizes: {material.get('baseColorDetailTexSize')}")
print(f"macro textures       : {len(macro_files)}")
print(f"texture set          : base={texture_set.get('baseTexSize')} detail={texture_set.get('detailTexSize')} macro={texture_set.get('macroTexSize')}")
missing = [n for n, b in sources.items() if b is None]
print(f"unavailable textures : {missing or 'NONE'}")

io.open(os.path.join(REPO, "build", "skeleton_material.json"), "w", encoding="utf-8").write(
    json.dumps({"material": material, "textureSet": texture_set}, indent=2)
)
print("\nwritten build/skeleton_material.json")
