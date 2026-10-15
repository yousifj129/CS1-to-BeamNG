"""Ground buildings on the lowest point under their footprint, and restore the grass family."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- buildings: sample the footprint, sit on the lowest ground -------------------------
OLD = """            # Place the box on the reconstructed ground; top face at ground + height.
            bx, by, _ = building.position.beamng()
            ground = self.ground_height(bx, by)

            yaw = yaw_to_beamng(building.angle_radians)
"""
NEW = """            bx, by, _ = building.position.beamng()
            yaw = yaw_to_beamng(building.angle_radians)

            # Ground the building on the LOWEST surface under its whole footprint.  Sampling only
            # the centre is what made buildings float: on a slope the centre can sit well above a
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
                ground = min(probes)
                # Sink a little so an uneven footprint cannot leave a visible lip.
                ground -= 0.15
"""
if OLD not in src:
    raise SystemExit("building placement anchor not found")
src = src.replace(OLD, NEW, 1)

# ---- terrain back to grass -------------------------------------------------------------
OLD_ENGINE = src[src.index("_ASPHALT = "):src.index("}", src.index("heightMacroTex")) + 1]
NEW_ENGINE = '''_TERRAIN = "/assets/materials/terrain"

# Grass family, using the same proven structure as the asphalt test that rendered correctly:
# five local base textures at 2048 plus ten engine detail/macro references at 1024.
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

# ---- vertical scale: allow the real height so nothing floats ---------------------------
src = src.replace("uniform * 1.6", "uniform * 3.0", 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("footprint grounding :", "LOWEST surface under its whole footprint" in src)
print("grass family         :", "grass/ind_grass/t_ind_grass_b.png" in src)
print("groundmodel GRASS    :", '"groundmodelName": "GRASS"' in src)
print("vertical cap 3.0x    :", "uniform * 3.0" in src)
