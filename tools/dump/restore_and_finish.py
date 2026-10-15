"""
Restore the last good converter and apply the two remaining fixes cleanly.

`build/beamng_convert.py.pre_ground` is the state with chained roads working.  Onto it:

  * ground each building on the LOWEST surface under its footprint (fixes floating)
  * raise the vertical scale ceiling so a tall building reaches the ground
  * put the terrain back on the grass family, keeping the structure proven by the asphalt test
"""

import io
import os
import shutil

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
BACKUP = os.path.join(REPO, "build", "beamng_convert.py.pre_ground")

shutil.copyfile(BACKUP, TARGET)
src = io.open(TARGET, encoding="utf-8").read()
print("restored:", len(src.split("\n")), "lines")


def sub(old, new, label):
    global src
    if old not in src:
        print("  SKIP (anchor missing):", label)
        return False
    src = src.replace(old, new, 1)
    print("  applied:", label)
    return True


# ---- 1. buildings sit on the lowest ground under their footprint -----------------------
sub(
    """            # Place the box on the reconstructed ground; top face at ground + height.
            bx, by, _ = building.position.beamng()
            ground = self.ground_height(bx, by)

            yaw = yaw_to_beamng(building.angle_radians)
""",
    """            bx, by, _ = building.position.beamng()
            yaw = yaw_to_beamng(building.angle_radians)

            # Ground the building on the LOWEST surface under its whole footprint.  Sampling only
            # the centre is what made buildings float: on a slope the centre sits well above a
            # downhill corner, leaving the mesh hovering with daylight underneath.
            ground = self.ground_height(bx, by)
            if self.terrain is not None:
                cos_a, sin_a = math.cos(yaw), math.sin(yaw)
                probes = [ground]
                for ox, oy in (
                    (-half_w, -half_l), (half_w, -half_l), (-half_w, half_l), (half_w, half_l),
                    (-half_w, 0.0), (half_w, 0.0), (0.0, -half_l), (0.0, half_l),
                ):
                    # Rotate the corner offset by the building's yaw.
                    rx = ox * cos_a - oy * sin_a
                    ry = ox * sin_a + oy * cos_a
                    probes.append(self.ground_height(bx + rx, by + ry))
                ground = min(probes) - 0.15
""",
    "footprint grounding",
)

# ---- 2. allow the true height so a tall building reaches the ground --------------------
sub("uniform * 1.6", "uniform * 3.0", "vertical scale ceiling 3.0x")

# ---- 3. terrain back to grass ----------------------------------------------------------
OLD_ENGINE = """CS1_TERRAIN_ENGINE_TEX = {
    \"baseColorDetailTex\": \"/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_b.png\",
    \"normalDetailTex\": \"/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_nm.png\",
    \"roughnessDetailTex\": \"/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_r.png\",
    \"aoDetailTex\": \"/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_ao.png\",
    \"heightDetailTex\": \"/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_h.png\",
    \"baseColorMacroTex\": \"/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_b.png\",
    \"normalMacroTex\": \"/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_nm.png\",
    \"roughnessMacroTex\": \"/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_r.png\",
    \"aoMacroTex\": \"/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_ao.png\",
    \"heightMacroTex\": \"/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_h.png\",
}"""
NEW_ENGINE = """# Grass family, with the same structure that the asphalt test proved renders correctly:
# five local base textures at 2048 plus ten engine detail/macro references at 1024.
_TERRAIN = "/assets/materials/terrain"

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
}"""
sub(OLD_ENGINE, NEW_ENGINE, "grass detail/macro family")
sub('"groundmodelName": "ASPHALT",\n            "annotation": "ASPHALT",',
    '"groundmodelName": "GRASS",\n            "annotation": "GRASS",',
    "groundmodel GRASS")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print()
print("grass detail:", "grass/ind_grass/t_ind_grass_b.png" in src)
print("groundmodel :", '"groundmodelName": "GRASS"' in src)
print("cap 3.0     :", "uniform * 3.0" in src)
print("grounding   :", "LOWEST surface under its whole footprint" in src)
