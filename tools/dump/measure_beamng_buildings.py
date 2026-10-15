"""
Pick real BeamNG building shapes to stand in for CS1 buildings, and measure them.

Two useful families exist in the shipped content:

  * levels/italy/art/shapes/buildings/ind_bld_<w>x<d>.dae  -- industrial blocks whose footprint
    is in the filename (8x8 up to 24x60), ideal for sizing.
  * levels/west_coast_usa/art/shapes/buildings/city_block*.dae and city_west*.dae -- town blocks.

For each candidate this reads the Collada POSITION accessor and reports the model's bounding box,
so the converter can scale a model to a CS1 building's real footprint instead of guessing.
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

BEAMNG = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"
LEVELS = os.path.join(BEAMNG, "content", "levels")
NS = "{http://www.collada.org/2005/11/COLLADASchema}"

CANDIDATES = {
    "italy.zip": r"levels/italy/art/shapes/buildings/",
    "west_coast_usa.zip": r"levels/west_coast_usa/art/shapes/buildings/",
}

WANTED = re.compile(
    r"^(ind_bld_\d+x\d+|city_block\d+|city_west\d+|church|condo_cylindrical|buildingblock_\w+)\.dae$",
    re.I,
)


def bounding_box(blob: bytes) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Read the first POSITION float_array and return (min, max)."""
    root = ET.fromstring(blob)
    for source in root.iter(NS + "source"):
        array = source.find(NS + "float_array")
        if array is None or not (array.text or "").strip():
            continue
        acc = source.find(NS + "technique_common/" + NS + "accessor")
        if acc is None:
            continue
        stride = int(acc.get("stride", "3"))
        if stride != 3:
            continue
        values = [float(v) for v in array.text.split()]
        xs, ys, zs = values[0::3], values[1::3], values[2::3]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))
    raise ValueError("no POSITION data")


results: List[Tuple[str, str, Tuple[float, float, float]]] = []

for archive_name, prefix in CANDIDATES.items():
    path = os.path.join(LEVELS, archive_name)
    if not os.path.isfile(path):
        continue
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            base = os.path.basename(entry.filename)
            if not (entry.filename.startswith(prefix) and WANTED.match(base)):
                continue
            try:
                blob = archive.read(entry)
                lo, hi = bounding_box(blob)
            except Exception as exc:
                print(f"  skip {base}: {exc}")
                continue
            size = (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
            level = archive_name.replace(".zip", "")
            results.append((base, f"/levels/{level}/{entry.filename.split('art/', 1)[1].join(['art/', ''])}".replace("art/art/", "art/"), size))

print(f"{'model':<26} {'W':>8} {'D':>8} {'H':>8}   path")
print("-" * 110)
for base, path, size in sorted(results, key=lambda r: r[2][0] * r[2][1]):
    print(f"{base:<26} {size[0]:>8.2f} {size[1]:>8.2f} {size[2]:>8.2f}   {path}")

print()
print(f"total measured: {len(results)}")
