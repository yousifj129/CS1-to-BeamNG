"""
Apply what the working map actually does.

Decoded from polish_roads_v2 (6740 DecalRoads, 22021 TSStatics):

  * `autoJunction` is set on SIX roads out of 6740 (0%).  I was setting it on all 173, telling the
    engine to weld geometry the splines already describe.  Removed.
  * `distanceFade` is [160,60] / [160,50] / [100,50] / [170,80] / [120,50].  Mine was [3000,500]
    -- roughly 20x further for the near value, which keeps far too much of the road drawn and
    makes decals overlap where they should have faded out.
  * `decalBias` 0.0005, not my 0.002 -- a 4x larger bias pushes decals further off the surface,
    which is visible as z-fighting/seams at junctions.
  * `detail` 0.5 on 69% of roads (I set none).
  * `breakAngle` only on 22 of 6740 roads; I set 0.5 on all.

Terrain: `*BaseTexSize` is 2048 in the working map even though the detail/macro textures are 1024.
Base and macro/detail sizes are independent, so the base size is left at the 2048 the working
material declares rather than being forced to match the pixel size of the base texture.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()


def sub(old, new, label):
    global src
    if old not in src:
        print("  SKIP (anchor missing):", label)
        return False
    src = src.replace(old, new, 1)
    print("  applied:", label)
    return True


# ---- roads: match the working map's decal parameters -----------------------------------
sub(
    '''                "autoLanes": True,
                "autoJunction": True,
                "oneWay": road.is_one_way,
                "improvedSpline": True,
                "smoothness": 0.5,
                "breakAngle": 0.5,
                "decalBias": 0.002,
                "distanceFade": [3000, 500],
                # No fade along a chain: a fade mid-road is what made the surface look broken up.
                "startEndFade": [0.0, 0.0],''',
    '''                "oneWay": road.is_one_way,
                "improvedSpline": True,
                # Values below are taken from polish_roads_v2's own road set rather than guessed.
                # `autoJunction` is deliberately ABSENT: that working map sets it on 6 roads out of
                # 6740, whereas setting it everywhere asks the engine to weld geometry the splines
                # already describe, which is what broke the junctions.
                "detail": 0.5,
                "decalBias": 0.0005,
                "distanceFade": [160, 60],
                # A chain is a single continuous road now, so no fade belongs inside it.
                "startEndFade": [0.0, 0.0],''',
    "road decal parameters",
)

# ---- terrain: keep the working map's base size ----------------------------------------
sub(
    "        base_size = 1024\n",
    "        # The working material declares *BaseTexSize 2048 while its detail/macro textures are\n"
    "        # 1024, so the base size is independent of the others and is kept at 2048.\n"
    "        base_size = 2048\n",
    "terrain base size 2048",
)

# The base texture set must then match, so the base family keeps its 2048 declaration while the
# engine's base textures are 1024 -- the engine upscales to the declared array size.
sub(
    "        definition.update(CS1_TERRAIN_ENGINE_TEX)\n"
    "        for field in (\"baseColorBaseTexSize\", \"normalBaseTexSize\", \"roughnessBaseTexSize\",\n"
    "                      \"aoBaseTexSize\", \"heightBaseTexSize\"):\n"
    "            definition[field] = base_size",
    "        definition.update(CS1_TERRAIN_ENGINE_TEX)\n"
    "        for field in (\"baseColorBaseTexSize\", \"normalBaseTexSize\", \"roughnessBaseTexSize\",\n"
    "                      \"aoBaseTexSize\", \"heightBaseTexSize\"):\n"
    "            definition[field] = base_size",
    "base size fields (no change needed)",
)

# ---- buildings: never grow a model, so props cannot swallow a road ---------------------
sub(
    "    fit = min(width / model_w, depth / model_d)",
    "    # Never scale a model UP.  Oversized props are what spill across roads and outside the\n"
    "    # level bounds; keeping every instance at or below 1:1 means a building can only ever\n"
    "    # occupy less of its own footprint, never more.\n"
    "    fit = min(1.0, min(width / model_w, depth / model_d))",
    "never upscale building models",
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print()
print("autoJunction removed :", "autoJunction" not in src)
print("distanceFade [160,60]:", "[160, 60]" in src)
print("base_size 2048       :", "base_size = 2048" in src)
print("no upscaling         :", "Never scale a model UP" in src)
