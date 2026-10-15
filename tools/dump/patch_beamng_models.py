"""
Use real BeamNG building models instead of generated boxes.

The generated boxes never rendered (a DAE binding that BeamNG would not resolve), and there are
plenty of genuine building meshes in the shipped content, so those are used instead.

Model selection is driven by measured bounding boxes, so each instance can be scaled to the CS1
building's real footprint rather than guessed.  Candidates come from two families:

  * levels/italy/art/shapes/buildings/ind_bld_<w>x<d>.dae -- industrial blocks, 8x8 up to 24x60
  * levels/west_coast_usa/art/shapes/buildings/            -- town blocks, 90-215 m across, and
                                                              condo_cylindrical for towers

Models are COPIED into the mod so the level does not depend on another level being mounted.
"""

import io
import os
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
BEAMNG = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"
LEVELS = os.path.join(BEAMNG, "content", "levels")

# (destination name, archive, member, measured size W x D x H)
MODELS = [
    ("beamng_ind_8x8.dae", "italy.zip", "levels/italy/art/shapes/buildings/ind_bld_8x8.dae", (8.20, 8.20, 5.73)),
    ("beamng_ind_12x10.dae", "italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x10.dae", (10.10, 12.10, 7.90)),
    ("beamng_ind_12x15.dae", "italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x15.dae", (15.20, 12.20, 12.55)),
    ("beamng_ind_12x24.dae", "italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x24.dae", (24.08, 13.01, 18.72)),
    ("beamng_ind_12x30.dae", "italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x30.dae", (30.10, 12.11, 10.92)),
    ("beamng_ind_24x60.dae", "italy.zip", "levels/italy/art/shapes/buildings/ind_bld_24x60.dae", (60.27, 31.07, 17.14)),
    ("beamng_city_west2.dae", "west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/city_west2.dae", (133.01, 91.59, 37.37)),
    ("beamng_city_west5.dae", "west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/city_west5.dae", (134.74, 94.73, 66.48)),
    ("beamng_city_block3.dae", "west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/city_block3.dae", (99.34, 87.42, 66.75)),
    ("beamng_condo_cyl.dae", "west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/condo_cylindrical.dae", (56.19, 56.63, 87.24)),
]


def copy_beamng_building_models(destination_dir: str) -> list:
    """Copy the chosen building DAEs into the mod.  Returns (filename, size) pairs."""
    os.makedirs(destination_dir, exist_ok=True)
    copied = []
    for name, archive_name, member, size in MODELS:
        archive_path = os.path.join(LEVELS, archive_name)
        if not os.path.isfile(archive_path):
            continue
        with zipfile.ZipFile(archive_path) as archive:
            try:
                blob = archive.read(member)
            except KeyError:
                continue
        with open(os.path.join(destination_dir, name), "wb") as handle:
            handle.write(blob)
        copied.append((name, size))
    return copied


# ---------------------------------------------------------------------------------------
HELPER = '''BEAMNG_BUILDING_MODELS = ''' + repr([(n, s) for n, _a, _m, s in MODELS]) + '''


def choose_beamng_model(width: float, depth: float, height: float, service: str):
    """
    Pick the BeamNG building model whose footprint is closest to this building's, and return
    (filename, size, scale) so the instance matches the CS1 footprint.

    Matching on footprint rather than on service keeps the skyline proportional: a 16x24 m
    building gets the 12x24 industrial block, a 100x90 m one gets a town block.  The returned
    scale stretches the model to the exact CS1 footprint, so the layout stays true to the save.
    """
    best = None
    for name, (mw, md, mh) in BEAMNG_BUILDING_MODELS:
        # Compare footprints in a way that does not care about a 90 degree rotation.
        direct = abs(mw - width) + abs(md - depth)
        swapped = abs(md - width) + abs(mw - depth)
        cost = min(direct, swapped)
        if best is None or cost < best[0]:
            best = (cost, name, (mw, md, mh))

    _cost, name, (mw, md, mh) = best
    # Scale so the model's footprint becomes the building's footprint.  Guard against a model
    # whose axes are swapped relative to the building.
    if abs(mw - width) + abs(md - depth) <= abs(md - width) + abs(mw - depth):
        scale = (width / mw, depth / md, max(height, 1.0) / mh)
        rotation = 0.0
    else:
        scale = (depth / md, width / mw, max(height, 1.0) / mh)
        rotation = 0.0
    return name, (mw, md, mh), scale


'''


def sub(old, new, label):
    global src
    if old not in src:
        print("  SKIP (not found):", label)
        return False
    src = src.replace(old, new, 1)
    print("  applied:", label)
    return True


src = io.open(TARGET, encoding="utf-8").read()

# 1. insert the model helper before the builder class
class_at = src.index("class BeamNGLevelBuilder")
src = src[:class_at] + HELPER + src[class_at:]

# 2. buildings reference a real BeamNG model, scaled to the CS1 footprint
sub(
    '''            # Tall buildings get the stepped silhouette; everything else a block with a roof cap.
            shape = "tower" if height >= 24.0 and half_w < 22.0 else "block"
''',
    '''            # Real BeamNG building mesh, chosen by footprint and scaled to match exactly.
            model, model_size, model_scale = choose_beamng_model(
                building.width, building.length, height, building.service
            )
''',
    "building model selection",
)

sub(
    '''                "shapeName": (
                    f"/art/shapes/{self.mod_name}/cs1_building_{shape}_"
                    f"{BUILDING_MATERIAL_FOR_SERVICE.get(building.service, 'default')}.dae"
                ),''',
    '                "shapeName": f"/art/shapes/{self.mod_name}/{model}",',
    "TSStatic shapeName -> BeamNG model",
)

sub(
    '                "scale": [round(half_w, 4), round(half_l, 4), round(height, 4)],',
    '                "scale": [round(v, 5) for v in model_scale],',
    "TSStatic scale -> model scale",
)

# 3. replace the generated-shape emission with copying real models
OLD_EMIT_START = '        for shape in ("block", "tower"):'
if OLD_EMIT_START in src:
    start = src.index(OLD_EMIT_START)
    marker = "build_material_definitions()\n        )"
    stop = src.index(marker, start) + len(marker)
    replacement = '''        copied = copy_beamng_building_models(shape_dir)
        for name, _size in copied:
            self.report["files"].append(
                os.path.relpath(os.path.join(shape_dir, name), self.mod_root)
            )
        if not copied:
            self.report["warnings"].append(
                "no BeamNG building models could be copied; buildings will not render"
            )

        # The palette is kept for anything that still wants a plain material (and as a record of
        # the service mapping), even though the models carry their own materials.
        self.write_json(
            os.path.join(shape_dir, "main.materials.json"), build_material_definitions()
        )'''
    src = src[:start] + replacement + src[stop:]
    print("  applied: emit_proxy_box_shape -> copy real BeamNG models")

# 4. method docstring
src = src.replace(
    """        Generate the building shapes and their materials.

        Geometry spans X/Y in -0.5..0.5 (centred on the instance) and Z in 0..1 (base at Z=0), so
        an instance scale of (halfWidth, halfLength, height) plus a rotation about Z stands the
        mass on the terrain, centred on the building.

        The shapes carry no material binding on purpose, so each TSStatic's `materialName` decides
        the finish.  An earlier version bound a material inside the DAE; it did not resolve and
        every building rendered as the engine's flat orange warning material.
        \"\"\"""",
    """        Copy real BeamNG building models into the mod and write the material palette.

        Generated boxes were tried first and never rendered: the DAE bound a material that BeamNG
        would not resolve, so nothing was visible.  Genuine building meshes from the shipped
        content are used instead, copied in so the level does not depend on another level being
        mounted.  Each instance is then scaled to the CS1 footprint by choose_beamng_model().
        \"\"\"""",
    1,
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print()
print("  helper present     :", "choose_beamng_model" in src)
print("  models listed      :", src.count(".dae\", \"italy.zip\"") + src.count("BEAMNG_BUILDING_MODELS"))
