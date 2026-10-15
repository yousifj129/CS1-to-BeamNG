"""
Determine each shape's real axes, so size and centre come from one consistent measurement.

The size table and the mesh disagree about which axis is height.  Measured extents:

    ind_bld_8x8    [8.2, 8.2, 5.73]      table (8.2, 8.2, 5.73)
    ind_bld_12x30  [30.22, 12.3, 10.92]  table (30.10, 12.11, 10.92)
    city_block3    [624.91, 370.07, 66.75]  table (99.34, 87.42, 66.75)   <- 6x too big

`city_block3` being six times the table size means its geometry is stored with node transforms I am
not applying, so its raw vertex bounds are unusable.  This prints enough per shape to tell which
axis is height and which shapes can be trusted.
"""

import os
import re
import zipfile

GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"

SHAPES = [
    ("italy.zip", "ind_bld_8x8.dae", (8.20, 8.20, 5.73)),
    ("italy.zip", "ind_bld_12x10.dae", (10.10, 12.10, 7.90)),
    ("italy.zip", "ind_bld_12x30.dae", (30.10, 12.11, 10.92)),
    ("italy.zip", "ind_bld_24x60.dae", (60.27, 31.07, 17.14)),
    ("west_coast_usa.zip", "city_block3.dae", (99.34, 87.42, 66.75)),
    ("west_coast_usa.zip", "condo_cylindrical.dae", (56.19, 56.63, 87.24)),
]


def nums(text):
    return [float(v) for v in text.split()]


for archive, base, table in SHAPES:
    member = None
    with zipfile.ZipFile(os.path.join(GAME, "content", "levels", archive)) as z:
        for n in z.namelist():
            if n.endswith("/" + base):
                member = n
                break
        text = z.read(member).decode("utf-8", "replace")

    lo = [1e18] * 3
    hi = [-1e18] * 3
    for _gid, body in re.findall(r'<geometry[^>]*id="([^"]+)"[^>]*>(.*?)</geometry>', text, re.S):
        # Only the POSITION source: the one whose id mentions position, or the first source if the
        # accessor stride/name is unavailable.
        srcs = re.findall(r"<source[^>]*>(.*?)</source>", body, re.S)
        chosen = None
        for s in srcs:
            if "position" in s.lower():
                chosen = s
                break
        if chosen is None and srcs:
            # Fall back to the largest float array, which is almost always the positions.
            best = None
            for s in srcs:
                arr = re.search(r"<float_array[^>]*>(.*?)</float_array>", s, re.S)
                if not arr:
                    continue
                vals = nums(arr.group(1))
                if best is None or len(vals) > len(best):
                    best = vals
            if best is None:
                continue
            values = best
        else:
            arr = re.search(r"<float_array[^>]*>(.*?)</float_array>", chosen, re.S)
            if not arr:
                continue
            values = nums(arr.group(1))

        if len(values) < 3:
            continue
        for axis in range(3):
            col = values[axis::3]
            lo[axis] = min(lo[axis], min(col))
            hi[axis] = max(hi[axis], max(col))

    size = [round(hi[i] - lo[i], 2) for i in range(3)]
    centre = [round((hi[i] + lo[i]) * 0.5, 2) for i in range(3)]
    print(f"{base:<26} table {table}")
    print(f"{'':<26} mesh  size {size}   centre {centre}")
    print(f"{'':<26} ratio to table: "
          f"{[round(size[i] / table[i], 2) for i in range(3)]}")
    print()
