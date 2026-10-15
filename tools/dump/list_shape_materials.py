"""
Which material names do the base-game building shapes actually declare?

The window-material aliases are only useful if their names match what the shapes ask for.  This
reads the `<library_materials>` block of every shape we reference and lists the real material
names, so the alias list can be based on measurement instead of assumption.
"""

import os
import re
import zipfile
from collections import Counter

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"

SHAPES = [
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_8x8.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x10.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x24.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_12x30.dae"),
    ("italy.zip", "levels/italy/art/shapes/buildings/ind_bld_24x60.dae"),
    ("west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/city_west2.dae"),
    ("west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/city_block3.dae"),
    ("west_coast_usa.zip", "levels/west_coast_usa/art/shapes/buildings/condo_cylindrical.dae"),
]

all_names = Counter()
writes = Counter()
per_shape = {}

for archive_name, member in SHAPES:
    path = os.path.join(GAME, "content", "levels", archive_name)
    if not os.path.isfile(path):
        print("missing archive:", archive_name)
        continue
    with zipfile.ZipFile(path) as z:
        try:
            text = z.read(member).decode("utf-8", "replace")
        except KeyError:
            print("missing member:", member)
            continue

    # Material library entries: <material id="..." name="...">
    names = re.findall(r'<material\s+id="([^"]+)"\s+name="([^"]+)"', text)
    # And the symbols bound by instance_material.
    symbols = re.findall(r'<instance_material\s+symbol="([^"]+)"', text)

    shape = os.path.basename(member)
    per_shape[shape] = (len(names), len(symbols))
    for _id, name in names:
        all_names[name] += 1
    for s in symbols:
        writes[s] += 1

print(f"{'shape':<30}{'materials':>10}{'bindings':>10}")
print("-" * 52)
for shape, (nm, sy) in sorted(per_shape.items()):
    print(f"{shape:<30}{nm:>10}{sy:>10}")

print()
print("ALL distinct material names declared by these shapes:")
for name, count in all_names.most_common():
    print(f"   {count:>3}x  {name}")

print()
print("ALL distinct instance_material symbols (what the geometry binds):")
for name, count in writes.most_common():
    print(f"   {count:>3}x  {name}")

# Anything that looks like a window / glass / door material.
print()
print("names that look like glazing:")
pattern = re.compile(r"(glass|window|glaz|pane|facade|door)", re.I)
found = [n for n in all_names if pattern.search(n)]
for n in sorted(set(found)):
    print("   ", n)
if not found:
    print("    (none)")
