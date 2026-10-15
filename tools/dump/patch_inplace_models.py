"""
Reference base-game building shapes in place instead of copying them into the mod.

Copying the DAEs broke them: each copied file still contains `<instance_material>` entries whose
targets are defined in the SOURCE level's material library, which our mod does not have.  The
engine could not resolve the geometry's materials and fell back to its "No Mesh" placeholder on
every building.

Working maps solve this by referencing shapes in place across levels.  Measured directly from
polish_roads_v2:

    /levels/derby/art/shapes/buildings/ind_bld_04.dae
    /levels/Industrial/art/shapes/misc/containers_40_brown.dae
    /levels/italy/art/shapes/buildings/ind_bld_portcrane.dae

It uses 208 shapes from Industrial, 15 from italy and 8 from derby that way, so the engine
resolves cross-level shape paths, and does so with the source level's own materials intact.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- 1. model table gains the level prefix ---------------------------------------------
OLD_TABLE_START = "BEAMNG_BUILDING_SOURCES = ["
start = src.index(OLD_TABLE_START)
end = src.index("]", src.index("beamng_condo_cyl.dae", start)) + 1

NEW_TABLE = '''BEAMNG_BUILDING_SOURCES = [
    # (filename, level, archive member, measured W x D x H)
    # Referenced IN PLACE rather than copied: a copied DAE keeps <instance_material> targets that
    # belong to the source level's material library, which our mod does not ship, and the engine
    # then shows "No Mesh" for every instance.
    ("beamng_ind_8x8.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_8x8.dae", (8.20, 8.20, 5.73)),
    ("beamng_ind_12x10.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_12x10.dae", (10.10, 12.10, 7.90)),
    ("beamng_ind_12x15.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_12x15.dae", (15.20, 12.20, 12.55)),
    ("beamng_ind_12x24.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_12x24.dae", (24.08, 13.01, 18.72)),
    ("beamng_ind_12x30.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_12x30.dae", (30.10, 12.11, 10.92)),
    ("beamng_ind_24x60.dae", "italy", "levels/italy/art/shapes/buildings/ind_bld_24x60.dae", (60.27, 31.07, 17.14)),
    ("beamng_city_west2.dae", "west_coast_usa", "levels/west_coast_usa/art/shapes/buildings/city_west2.dae", (133.01, 91.59, 37.37)),
    ("beamng_city_west5.dae", "west_coast_usa", "levels/west_coast_usa/art/shapes/buildings/city_west5.dae", (134.74, 94.73, 66.48)),
    ("beamng_city_block3.dae", "west_coast_usa", "levels/west_coast_usa/art/shapes/buildings/city_block3.dae", (99.34, 87.42, 66.75)),
    ("beamng_condo_cyl.dae", "west_coast_usa", "levels/west_coast_usa/art/shapes/buildings/condo_cylindrical.dae", (56.19, 56.63, 87.24)),
]'''

src = src[:start] + NEW_TABLE + src[end:]

# ---- 2. model lookup keeps the VFS path, drops copying ---------------------------------
src = src.replace(
    'BEAMNG_BUILDING_MODELS = [(name, size) for name, _a, _m, size in BEAMNG_BUILDING_SOURCES]',
    'BEAMNG_BUILDING_MODELS = [\n'
    '    (name, level, member, size) for name, level, member, size in BEAMNG_BUILDING_SOURCES\n'
    ']',
    1,
)

# ---- 3. choose_beamng_model returns the in-place VFS path -------------------------------
src = src.replace(
    '''    best = None
    for name, (mw, md, mh) in BEAMNG_BUILDING_MODELS:''',
    '''    best = None
    for name, level, member, (mw, md, mh) in BEAMNG_BUILDING_MODELS:''',
    1,
)
src = src.replace(
    '''        if best is None or cost < best[0]:
            best = (cost, name, (mw, md, mh))

    _cost, name, (mw, md, mh) = best''',
    '''        if best is None or cost < best[0]:
            best = (cost, name, level, member, (mw, md, mh))

    _cost, name, level, member, (mw, md, mh) = best''',
    1,
)
src = src.replace(
    '''    return name, (mw, md, mh), scale''',
    '''    # Referenced in place, so the source level's own materials stay intact.
    return f"/{member}", (mw, md, mh), scale''',
    1,
)

# ---- 4. the TSStatic uses the returned path directly ------------------------------------
src = src.replace(
    '                "shapeName": f"/art/shapes/{self.mod_name}/{model}",',
    '                # `model` is already a full VFS path such as\n'
    '                # /levels/italy/art/shapes/buildings/ind_bld_12x24.dae\n'
    '                "shapeName": model,',
    1,
)

# ---- 5. stop copying the models ---------------------------------------------------------
OLD_COPY = src.index("        copied = copy_beamng_building_models(shape_dir)")
OLD_END = src.index("        self.write_json(\n            os.path.join(shape_dir, \"main.materials.json\"), build_material_definitions()\n        )", OLD_COPY)
NEW_COPY = '''        # Shapes are referenced in place from the base game, so nothing is copied here.  The
        # material palette is still written for the road/lights materials.
'''
src = src[:OLD_COPY] + NEW_COPY + src[OLD_END:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("table has level column :", '("beamng_ind_8x8.dae", "italy"' in src)
print("returns in-place path  :", 'return f"/{member}"' in src)
print("shapeName uses model   :", '"shapeName": model,' in src)
print("copy call removed      :", "copy_beamng_building_models(shape_dir)" not in src)
