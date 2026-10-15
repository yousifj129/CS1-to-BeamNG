"""
Compare terrain footprint and heightmap size between our generated level and the shipped ones.

The question: is a 17 km square at 8192x8192 (67 M height samples) inside the range BeamNG
actually ships, or is it an outlier that stresses the terrain renderer?
"""

import json
import os
import re
import zipfile

LEVELS = r"D:\SteamLibrary\steamapps\common\BeamNG.drive\content\levels"
OURS = r"D:\Developer\open source projects\cities-skylines-to-beamng-map\dist\cs1_cannes"


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


def scan(path):
    out = {"terrain": None, "block": None, "preview": False}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        out["preview"] = any(re.search(r"/_preview\.(png|jpg)$", n) for n in names)

        for name in names:
            if re.search(r"\.terrain\.json$", name):
                info = archive.getinfo(name)
                if 0 < info.file_size < 20000:
                    try:
                        out["terrain"] = json.loads(archive.read(name).decode("utf-8", "replace"))
                    except Exception:
                        pass
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
                        out["block"] = obj
                        break
            if out["terrain"] and out["block"]:
                break
    return out


print("=" * 108)
print("shipped levels: terrain grid vs world size")
print("=" * 108)
print(f"{'level':<24} {'grid':>7} {'squareSize':>11} {'world (m)':>11} {'samples (M)':>12} {'preview':>8}")
print("-" * 108)

rows = []
for name in sorted(os.listdir(LEVELS)):
    if not name.endswith(".zip"):
        continue
    try:
        info = scan(os.path.join(LEVELS, name))
    except Exception as exc:
        print(f"{name:<24} scan failed: {exc}")
        continue

    terrain = info["terrain"] or {}
    block = info["block"] or {}
    grid = terrain.get("size")
    square = block.get("squareSize") or 1
    if isinstance(grid, int):
        world = grid * square
        samples = grid * grid / 1e6
        rows.append((name, grid, square, world, samples, info["preview"]))
        print(f"{name[:24]:<24} {grid:>7} {square:>11} {world:>11,.0f} {samples:>12,.1f} "
              f"{'yes' if info['preview'] else 'NO':>8}")

print()
print("=" * 108)
print("our level")
print("=" * 108)
terrain_path = os.path.join(OURS, "levels", "Cannes", "Cannes.terrain.json")
block_path = os.path.join(OURS, "levels", "Cannes", "main", "MissionGroup", "items.level.json")
with open(terrain_path, encoding="utf-8") as handle:
    our_terrain = json.load(handle)
our_block = None
for obj in objects_from(open(block_path, encoding="utf-8").read()):
    if obj.get("class") == "TerrainBlock":
        our_block = obj
grid = our_terrain["size"]
square = our_block["squareSize"]
world = grid * square
print(f"{'Cannes (ours)':<24} {grid:>7} {square:>11} {world:>11,.0f} {grid * grid / 1e6:>12,.1f} "
      f"{'yes' if os.path.isfile(os.path.join(OURS, 'levels', 'Cannes', '_preview.png')) else 'NO':>8}")
print()
if rows:
    largest = max(r[3] for r in rows)
    biggest_grid = max(r[1] for r in rows)
    print(f"shipped world sizes : {min(r[3] for r in rows):,.0f} .. {largest:,.0f} m")
    print(f"shipped grid sizes  : {min(r[1] for r in rows)} .. {biggest_grid}")
    print(f"our grid is {grid / biggest_grid:.1f}x the largest shipped grid")
    print(f"our world is {world / largest:.1f}x the largest shipped world")
