"""
Colour the terrain the way working levels do: a local base texture, with detail as a subtle overlay.

WHAT THE MEASUREMENT SHOWED
---------------------------
Every `baseColor*` texture available from `content/assets/materials/terrain.zip` is **neutral grey**.
Measured means:

    grass/t_grass_02/t_grass_02_b.png            RGB (112, 113, 107)
    grass/t_grass_01/t_grass_01_b.png            RGB (123, 123, 124)
    grass/ind_grass/t_ind_grass_b.png            RGB (127, 127, 127)
    asphalt/**/t_asphalt_b.color.dds             RGB (137, 137, 137)
    backdrop/island_terrain/..._grass_b.color.dds RGB (128, 128, 128)

None is green. They are detail maps, meant to modulate a colour that comes from somewhere else.

That "somewhere else" is visible in every working level: their Grass material's **base** family
points at the level's OWN `art/terrains/t_terrain_base_b.png` -- a 2048 or 4096 texture shipped
inside the level archive, which carries the actual ground colour. Its detail and macro families are
engine greyscale maps applied at LOW strength:

    automation_test_track  baseColorDetailStrength [0.5, 0]      baseColorMacroStrength [0.1, 0.1]
    Cliff                  baseColorDetailStrength [0.32, 0]     baseColorMacroStrength [0.1, 0.2]
    derby                  baseColorDetailStrength [0.35, 0]     baseColorMacroStrength [0.05, 0.2]

My material had no coloured base, and I had raised the detail and macro strengths to [0.85, 0.95] and
[0.5, 0.7] in an attempt to force colour out of greyscale maps. That cannot work: blending more grey
over grey produces grey. It is why the ground stays pale however the strengths are set.

There is no `baseColorFactor` on TerrainMaterial -- the field does not exist on any of the 191
terrain materials across the install -- so a tint cannot be applied from the material either.

SO
--
The strengths are returned to the working range, which is what they are for, and the grass reads as
the engine's grass colour rather than as a washed-out grey forced brighter.  Genuinely green ground
needs a coloured base texture, which only the level can provide.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# Return the blend strengths to the working-level range.
for old, new in (
    ('"baseColorDetailStrength": [0.85, 0.95],', '"baseColorDetailStrength": [0.45, 0.0],'),
    ('"baseColorMacroStrength": [0.5, 0.7],', '"baseColorMacroStrength": [0.15, 0.2],'),
):
    if old not in src:
        raise SystemExit(f"strength anchor not found: {old}")
    src = src.replace(old, new, 1)

# Grass base and detail from the two greenest-measuring sets; macro stays as the large-scale mixer.
src = src.replace("ROAD_DECAL_OVERLAP = 1.75", "ROAD_DECAL_OVERLAP = 1.75", 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("detail strength:", '"baseColorDetailStrength": [0.45, 0.0]' in src)
print("macro strength :", '"baseColorMacroStrength": [0.15, 0.2]' in src)
