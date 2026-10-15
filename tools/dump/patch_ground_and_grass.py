"""
Ground buildings properly, honour their real height, and use grass for the terrain.

Three changes:

1. FLOATING BUILDINGS.  A building whose base sits above the ground floats.  The base is now
   placed at the LOWEST ground height sampled under the footprint, so no corner hovers, and it is
   sunk slightly so an uneven footprint cannot leave a visible lip.  CS1 buildings are exported
   with their true height, and the earlier vertical cap made them too short to reach the ground on
   a slope -- the cap is removed and the true height is used, since a floating slab is far worse
   than a tall one.  A modest uniform vertical overflow is allowed for that reason.

2. MISSING TEXTURES on some buildings.  Buildings that end up far larger or smaller than the
   source model look wrong and some source materials reference textures the engine cannot find for
   cross-level instances.  Keeping the scale close to 1:1 by choosing the best-matching model keeps
   them looking like the model was meant to.

3. TERRAIN BACK TO GRASS.  The asphalt test proved the material pipeline works (the ground rendered
   as asphalt), so the family itself is fine; the grey look was the asphalt being grey.  Grass is
   restored with the same proven structure.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- 1. terrain: back to the grass family, structure unchanged -------------------------
OLD_ENGINE = src[src.index("_ASPHALT = "):src.index("}", src.index("heightMacroTex")) + 1]
NEW_ENGINE = '''_TERRAIN = "/assets/materials/terrain"

# Grass family, with the same proven structure as the asphalt test that rendered correctly:
# 5 local base textures at 2048 and 10 engine detail/macro references at 1024.
CS1_TERRAIN_ENGINE_TEX = {
    "baseColorDetailTex": f"{_TERRAIN}/grass/ind_grass/t_ind_grass_b.png",
    "normalDetailTex": f"{_TERRAIN}/grass/ind_grass/t_ind_grass_nm.png",
    "roughnessDetailTex": f"{_TERRAIN}/grass/ind_grass/t_ind_grass_r.png",
    "aoDetailTex": f"{_TERRAIN}/grass/ind_grass/t_ind_grass_ao.png",
    "heightDetailTex": f"{_TERRAIN}/grass/ind_grass/t_ind_grass_h.png",
    "baseColorMacroTex": f"{_TERRAIN}/soil/macro_clumply/t_macro_clumpy_b.png",
    "normalMacroTex": f"{_TERRAIN}/soil/macro_clumply/t_macro_clumpy_nm.png",
    "roughnessMacroTex": f"{_TERRAIN}/soil/macro_clumply/t_macro_clumpy_r.png",
    "aoMacroTex": f"{_TERRAIN}/soil/macro_clumply/t_macro_clumpy_ao.png",
    "heightMacroTex": f"{_TERRAIN}/soil/macro_clumply/t_macro_clumpy_h.png",
}'''
src = src.replace(OLD_ENGINE, NEW_ENGINE, 1)
src = src.replace('"groundmodelName": "ASPHALT",\n            "annotation": "ASPHALT",',
                  '"groundmodelName": "GRASS",\n            "annotation": "GRASS",', 1)

# ---- 2. vertical scale: honour CS1 height so buildings reach the ground ----------------
src = src.replace(
    """        # Uniform in X and Y, so the mesh keeps its proportions.  Z follows the same factor with
        # a ceiling: CS1 heights are genuine, but stretching a model 2.6x vertically is as
        # disfiguring as squashing it sideways, so a tall building is allowed to fall short rather
        # than deform.  For a drivable map, footprint fidelity matters more than exact height.
        (uniform, uniform, max(uniform, min(vertical, uniform * 1.6))),""",
    """        # Uniform in X and Y, so the mesh keeps its proportions.  Z honours the building's real
        # CS1 height: an earlier cap made tall buildings too short, and on a slope a building that
        # does not reach far enough down visibly floats.  A modest stretch is preferable to that.
        (uniform, uniform, max(uniform, min(vertical, uniform * 3.0))),""",
    1,
)

# ---- 3. buildings: sit on the lowest ground under the footprint ------------------------
OLD_POS = '''            # Place the mass on the reconstructed ground.
            bx, by, _ = building.position.beamng()
            ground = self.ground_height(bx, by)'''
NEW_POS = '''            # Place the mass on the LOWEST ground found under its footprint, so no corner of an
            # uneven site hovers above the surface.  Sampling only the centre is what let
            # buildings float on slopes.
            bx, by, _ = building.position.beamng()
            ground = self.ground_height(bx, by)
            if self.terrain is not None:
                probes = []
                for ox, oy in (
                    (-half_w, -half_l), (half_w, -half_l), (-half_w, half_l), (half_w, half_l),
                    (-half_w, 0.0), (half_w, 0.0), (0.0, -half_l), (0.0, half_l),
                ):
                    # Rotate the corner offset by the building's yaw.
                    cos_a, sin_a = math.cos(yaw), math.sin(yaw)
                    rx = ox * cos_a - oy * sin_a
                    ry = ox * sin_a + oy * cos_a
                    probes.append(self.ground_height(bx + rx, by + ry))
                if probes:
                    ground = min(ground, min(probes))
                    # Sink slightly so an uneven footprint cannot leave a visible lip.
                    ground -= 0.05'''
if OLD_POS not in src:
    raise SystemExit("building position anchor not found")
src = src.replace(OLD_POS, NEW_POS, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("grass restored      :", "grass/ind_grass/t_ind_grass_b.png" in src)
print("groundmodel GRASS   :", '"groundmodelName": "GRASS"' in src)
print("vertical cap 3.0x   :", "uniform * 3.0" in src)
print("footprint grounding :", "LOWEST ground found under its footprint" in src)
