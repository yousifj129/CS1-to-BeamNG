"""
Terrain: use ONLY the engine's own grass textures, no custom or copied files.

The engine ships complete grass sets at 1024x1024, all in content/assets/materials/terrain.zip:

  base   /assets/materials/terrain/grass/t_grass_02/t_grass_02_{b,nm,r,ao,h}.png
  macro  /assets/materials/terrain/grass/macro_grass/t_macro_grass_{...}.png
  detail /assets/materials/terrain/grass/ind_grass/t_ind_grass_{...}.png

Every one of the fifteen slots now points into `/assets/`, so nothing is copied into the level and
there is no custom texture to get wrong.  This mirrors exactly how the asphalt family worked when
the ground rendered correctly -- the only difference is that these are grass.

Buildings: ground on the HIGHEST surface under the footprint.

The previous version used the LOWEST point and then subtracted 0.15 m, which drove buildings down
into the terrain -- the "clipped under the terrain" regression.  Sitting on the high point instead
means the base is never buried; the cost is a small visible gap over a dip, which is far less
objectionable than an intersecting building.
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


# ---- 1. engine-only grass texture references -------------------------------------------
start = src.index("CS1_TERRAIN_ENGINE_TEX = {")
end = src.index("}", start) + 1
NEW_TEX = '''CS1_TERRAIN_ENGINE_TEX = {
    "baseColorBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_b.png",
    "normalBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_nm.png",
    "roughnessBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_r.png",
    "aoBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_ao.png",
    "heightBaseTex": "/assets/materials/terrain/grass/t_grass_02/t_grass_02_h.png",
    "baseColorDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_b.png",
    "normalDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_nm.png",
    "roughnessDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_r.png",
    "aoDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_ao.png",
    "heightDetailTex": "/assets/materials/terrain/grass/ind_grass/t_ind_grass_h.png",
    "baseColorMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_b.png",
    "normalMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_nm.png",
    "roughnessMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_r.png",
    "aoMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_ao.png",
    "heightMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_h.png",
}'''
src = src[:start] + NEW_TEX + src[end:]
print("  applied: engine-only grass texture table")

# ---- 2. stop copying and stop pointing at local base textures --------------------------
sub(
    """        base_size = 2048
        copied = copy_base_terrain_textures(terrain_dir, base_size)
        for _name, path in sorted(copied.items()):
            self.report["files"].append(os.path.relpath(path, self.mod_root))
        if not copied:
            self.report["warnings"].append(
                "no base terrain textures could be copied; the ground will render untextured"
            )

        # Confirm the files really are the size we are about to declare.
        measured = [png_pixel_size(p) for p in copied.values()]
        measured = [m for m in measured if m]
        if measured:
            base_size = max(set(measured), key=measured.count)

        detail_size = 1024
        macro_size = 1024""",
    """        # Nothing is copied: every texture slot points into the engine's own library, exactly as
        # the asphalt family did when it rendered correctly.
        copied: Dict[str, str] = {}
        base_size = 1024
        detail_size = 1024
        macro_size = 1024""",
    "no texture copying",
)

sub(
    """        for field, filename in CS1_TERRAIN_BASE_TEX.items():
            definition[field] = f"{vfs}/{filename}"
        for field in ("baseColorBaseTexSize", "normalBaseTexSize", "roughnessBaseTexSize",
                      "aoBaseTexSize", "heightBaseTexSize"):
            definition[field] = base_size

        definition.update(CS1_TERRAIN_ENGINE_TEX)""",
    """        definition.update(CS1_TERRAIN_ENGINE_TEX)
        for field in ("baseColorBaseTexSize", "normalBaseTexSize", "roughnessBaseTexSize",
                      "aoBaseTexSize", "heightBaseTexSize"):
            definition[field] = base_size""",
    "base textures from engine table",
)

# Drop the local-texture mirroring, since there is nothing local any more.
sub(
    """        legacy = os.path.join(self.level_root, "art", "terrain")
        os.makedirs(legacy, exist_ok=True)
        for name, path in copied.items():
            with open(path, "rb") as source, open(os.path.join(legacy, name), "wb") as target:
                target.write(source.read())
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)
        self.write_json(os.path.join(legacy, "main.materials.json"), definitions)""",
    """        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)

        # Remove any terrain textures a previous build copied in, so no stale local file is used.
        import shutil as _shutil

        for _folder in ("terrains", "terrain"):
            _dir = os.path.join(self.level_root, "art", _folder)
            if not os.path.isdir(_dir):
                continue
            for _name in os.listdir(_dir):
                if _name.lower().endswith(".png"):
                    try:
                        os.remove(os.path.join(_dir, _name))
                    except OSError:
                        pass""",
    "drop local texture mirroring",
)

# ---- 3. buildings sit on the HIGHEST ground under the footprint ------------------------
sub(
    """            # Ground the building on the LOWEST surface under its whole footprint.  Sampling only
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
                ground = min(probes) - 0.15""",
    """            # Sit the building on the HIGHEST surface under its footprint.  Using the lowest point
            # and subtracting a margin drove buildings down into the terrain; the high point can
            # leave a small gap over a dip, which is much less objectionable than an intersection.
            ground = self.ground_height(bx, by)
            if self.terrain is not None:
                cos_a, sin_a = math.cos(yaw), math.sin(yaw)
                probes = [ground]
                for ox, oy in (
                    (-half_w, -half_l), (half_w, -half_l), (-half_w, half_l), (half_w, half_l),
                    (-half_w, 0.0), (half_w, 0.0), (0.0, -half_l), (0.0, half_l),
                ):
                    rx = ox * cos_a - oy * sin_a
                    ry = ox * sin_a + oy * cos_a
                    probes.append(self.ground_height(bx + rx, by + ry))
                ground = max(probes)""",
    "buildings on highest footprint point",
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print()
print("engine-only textures :", src.count("/assets/materials/terrain/grass"))
print("no base copy call    :", "copy_base_terrain_textures(terrain_dir" not in src)
print("highest footprint    :", "HIGHEST surface under its footprint" in src)
