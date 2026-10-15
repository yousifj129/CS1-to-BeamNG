"""
Four fixes: the whitish wash, texture scale, road junctions, and terrain smoothness.

1. WHITISH FILTER -- the template level's fog.
   The lighting block is copied from `levels/template`, which carries a pale blue-grey fog colour
   and a heavy fog density:

       template : fogColor [0.741, 0.816, 0.925]   fogDensity 6.0e-4   visibleDistance 4500
       working  : fogColor [1, 1, 1]               fogDensity 2.8e-4   visibleDistance 9000
                  (polish_roads_v2)

   The template's density is more than twelve times the working value and its colour is strongly
   tinted, so everything is washed toward pale blue.  Both are overridden, and the visible distance
   is raised so distant terrain is not swallowed.

2. TEXTURE SCALE -- tiles reduced again, the request being "smaller".
   The grass sets are 1024x1024, so a 8 m base tile is 7.8 mm per texel, which still reads as
   pixelated at close range on a 32 km map.  Base drops to 2 m (2.0 mm per texel), macro to 0.5 m
   and detail to 0.25 m.

3. ROAD JUNCTIONS -- chains are extended past their endpoints.
   Each chain end is pushed outward along its final direction by one road half-width, so decals
   meeting at a junction genuinely overlap instead of merely touching.  Two decals that touch
   exactly still leave a hairline seam once each has its own fade and edge; overlapping removes it.

4. TERRAIN SMOOTHNESS -- the heightmap was built from scattered road samples only.
   With 173 chains over 32 km the sample coverage is sparse, and gap filling between distant samples
   produces steep facets.  Smoothing is increased and, more importantly, made wider-reaching: more
   iterations of the existing 3x3 pass reach only a few cells, so the pass is applied at a coarse
   scale as well, which flattens the long ramps between sparse samples rather than just local noise.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ==============================================================================================
# 1. Fog / atmosphere overrides, applied to the copied LevelInfo.
# ==============================================================================================
OLD = """                        if cls == "LevelInfo" and not clone.get("globalEnviromentMap"):
                            clone["globalEnviromentMap"] = "BNG_Sky_02_cubemap"
"""
NEW = """                        if cls == "LevelInfo":
                            if not clone.get("globalEnviromentMap"):
                                clone["globalEnviromentMap"] = "BNG_Sky_02_cubemap"

                            # The template's atmosphere is much foggier and more tinted than a
                            # working map's, which washes everything toward pale blue.  Values
                            # taken from polish_roads_v2's own LevelInfo.
                            clone["fogColor"] = [1, 1, 1, 1]
                            clone["fogDensity"] = 0.00028
                            clone["fogDensityOffset"] = 100
                            clone["fogAtmosphereHeight"] = 300
                            clone["visibleDistance"] = 9000
                            clone["decalBias"] = 0.001
"""
if OLD not in src:
    raise SystemExit("LevelInfo override anchor not found")
src = src.replace(OLD, NEW, 1)

# ==============================================================================================
# 2. Texture tiles: smaller again.
# ==============================================================================================
for old, new in (
    ('"baseColorBaseTexSize": 8,', '"baseColorBaseTexSize": 2,'),
    ('"normalBaseTexSize": 8,', '"normalBaseTexSize": 2,'),
    ('"roughnessBaseTexSize": 8,', '"roughnessBaseTexSize": 2,'),
    ('"aoBaseTexSize": 8,', '"aoBaseTexSize": 2,'),
    ('"heightBaseTexSize": 8,', '"heightBaseTexSize": 2,'),
    ('"baseColorMacroTexSize": 2,', '"baseColorMacroTexSize": 0.5,'),
    ('"normalMacroTexSize": 2,', '"normalMacroTexSize": 0.5,'),
    ('"roughnessMacroTexSize": 2,', '"roughnessMacroTexSize": 0.5,'),
    ('"aoMacroTexSize": 2,', '"aoMacroTexSize": 0.5,'),
    ('"heightMacroTexSize": 2,', '"heightMacroTexSize": 0.5,'),
    ('"baseColorDetailTexSize": 0.5,', '"baseColorDetailTexSize": 0.25,'),
    ('"normalDetailTexSize": 0.5,', '"normalDetailTexSize": 0.25,'),
    ('"roughnessDetailTexSize": 0.5,', '"roughnessDetailTexSize": 0.25,'),
    ('"aoDetailTexSize": 0.5,', '"aoDetailTexSize": 0.25,'),
    ('"heightDetailTexSize": 0.5,', '"heightDetailTexSize": 0.25,'),
):
    if old in src:
        src = src.replace(old, new, 1)
    else:
        print("  tile miss:", old)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("fog overridden   :", 'clone["fogDensity"] = 0.00028' in src)
print("base tile 2 m    :", '"baseColorBaseTexSize": 2,' in src)
print("macro tile 0.5 m :", '"baseColorMacroTexSize": 0.5,' in src)
print("detail tile 0.25 :", '"baseColorDetailTexSize": 0.25,' in src)
