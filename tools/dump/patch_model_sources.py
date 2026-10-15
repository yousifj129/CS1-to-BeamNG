"""Add copy_beamng_building_models() and full model metadata to the converter."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

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

BLOCK = (
    "BEAMNG_BUILDING_SOURCES = "
    + repr(MODELS)
    + '''


def find_beamng_install() -> Optional[str]:
    """Locate the BeamNG install, for the building models and terrain textures."""
    candidates = [
        os.environ.get("BEAMNG_PATH"),
        r"D:\\\\SteamLibrary\\\\steamapps\\\\common\\\\BeamNG.drive",
        r"C:\\\\Program Files (x86)\\\\Steam\\\\steamapps\\\\common\\\\BeamNG.drive",
        r"C:\\\\Program Files\\\\Steam\\\\steamapps\\\\common\\\\BeamNG.drive",
        r"E:\\\\SteamLibrary\\\\steamapps\\\\common\\\\BeamNG.drive",
        r"D:\\\\Steam\\\\steamapps\\\\common\\\\BeamNG.drive",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(os.path.join(candidate, "BeamNG.drive.exe")):
            return candidate
    return None


def copy_beamng_building_models(destination_dir: str) -> List[Tuple[str, Tuple[float, float, float]]]:
    """
    Copy real BeamNG building models into the mod.

    The models are copied rather than referenced in place so the level does not depend on another
    level being mounted, and their measured sizes are carried alongside so
    choose_beamng_model() can scale each instance to the CS1 footprint.
    """
    import zipfile

    game = find_beamng_install()
    os.makedirs(destination_dir, exist_ok=True)
    copied: List[Tuple[str, Tuple[float, float, float]]] = []
    if not game:
        return copied

    levels_dir = os.path.join(game, "content", "levels")
    for name, archive_name, member, size in BEAMNG_BUILDING_SOURCES:
        archive_path = os.path.join(levels_dir, archive_name)
        if not os.path.isfile(archive_path):
            continue
        try:
            with zipfile.ZipFile(archive_path) as archive:
                blob = archive.read(member)
        except (KeyError, zipfile.BadZipFile):
            continue
        with open(os.path.join(destination_dir, name), "wb") as handle:
            handle.write(blob)
        copied.append((name, size))
    return copied


BEAMNG_BUILDING_MODELS = [(name, size) for name, _a, _m, size in BEAMNG_BUILDING_SOURCES]


'''
)

anchor = "BEAMNG_BUILDING_MODELS = " + repr([(n, s) for n, _a, _m, s in MODELS])
if anchor not in src:
    raise SystemExit("model table anchor not found")

src = src.replace(anchor, BLOCK.rstrip("\n"), 1)
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)

print("source table added :", "BEAMNG_BUILDING_SOURCES" in src)
print("install locator    :", "def find_beamng_install()" in src)
print("copy function      :", "def copy_beamng_building_models(" in src)
print("model table        :", "BEAMNG_BUILDING_MODELS = [(name, size)" in src)
