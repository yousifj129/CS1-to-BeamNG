"""
Correct the tile conformance rules.

They required a base >= 64 m and a macro >= 32 m, taken from polish_roads_v2's Grass where the base is
a **satellite photograph** stretched over the whole 2 km map and the macro is 80 m.

That reasoning does not transfer. Polish can stretch its base because a satellite photo has no usable
close-range normal detail. `t_forest_ground_02` is a close-up grass texture: at a 200 m tile its
normals are magnified ~200x, which is what made the ground dark, bluish and magenta-flecked, and its
grass blades smear into the "pixelated" look.

The real requirements are:

* every family tiles at a scale where its own detail is legible, and none is stretched so far that
  its normals dominate the shading;
* the three families differ, so no two apply the same map;
* the detail family is the finest.

The reference's own grass uses 2048 m for a photo base and 3 m for its detail -- so the *detail*
figure is the transferable one, and the base figure depends entirely on what the base image is.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

start = src.index("# Reference structure, from polish_roads_v2's Grass")
end = src.index('        mat.get("baseColorDetailTex") != mat.get("baseColorBaseTex"),', start)
end = src.index(")", end) + 1

NEW = '''# Tile scale.  The rule is NOT "base large, macro large" -- that came from polish_roads_v2's Grass,
# whose base is a satellite photograph stretched over a 2 km map and therefore has no usable
# close-range normal detail.  A close-up grass texture stretched to 200 m magnifies its normals
# ~200x, which is what made this level's ground dark and bluish.  What matters is that each family
# tiles where its own detail is legible, that none is stretched absurdly, and that they differ.
if mat:
    base_tile = mat.get("baseColorBaseTexSize")
    detail_tile = mat.get("baseColorDetailTexSize")
    macro_tile = mat.get("baseColorMacroTexSize")

    check(isinstance(base_tile, (int, float)) and 8 <= base_tile <= 64,
          "base tile is legible, not stretched or pixelated (8-64 m)",
          f"baseColorBaseTexSize={base_tile}")
    check(isinstance(detail_tile, (int, float)) and 0.5 <= detail_tile <= 12,
          "detail tile is fine (0.5-12 m); the reference's grass uses 3 m",
          f"baseColorDetailTexSize={detail_tile}")
    check(isinstance(macro_tile, (int, float)) and macro_tile > detail_tile,
          "macro tiles more coarsely than detail",
          f"macro={macro_tile} detail={detail_tile}")
    check(
        mat.get("baseColorDetailTex") != mat.get("baseColorBaseTex"),
        "base and detail use DIFFERENT textures (identical paths apply one map twice)",
        f"{str(mat.get('baseColorBaseTex')).rsplit('/', 1)[-1]} vs "
        f"{str(mat.get('baseColorDetailTex')).rsplit('/', 1)[-1]}",
    )'''

src = src[:start] + NEW + src[end:]

# Remove the other two now-contradictory checks elsewhere in the file.
for dead in (
    '''    check(isinstance(base_tile, (int, float)) and base_tile >= 64,
          "base colour layer is stretched, not tiled visibly (>= 64 m)",
          f"baseColorBaseTexSize={base_tile}")
''',
    '''    check(isinstance(macro_tile, (int, float)) and macro_tile >= 32,
          "macro layer tiles coarsely (>= 32 m), like the reference's 80 m",
          f"baseColorMacroTexSize={macro_tile}")
''',
    '''    check(mat.get("baseColorMacroTexSize", 1e9) < base_tile,
          "macro tile is finer than the base tile",
          f"macro={mat.get('baseColorMacroTexSize')} base={base_tile}")
''',
):
    src = src.replace(dead, "")

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("corrected the tile rules; syntax OK")
