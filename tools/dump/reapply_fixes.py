"""Reapply the fixes that the reconstruction pulled from an older backup class body."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
s = io.open(TARGET, encoding="utf-8").read()
original = s


def sub(old, new, label):
    global s
    if old not in s:
        print(f"  SKIP (not found): {label}")
        return False
    s = s.replace(old, new, 1)
    print(f"  applied: {label}")
    return True


# ---- 1. __init__: unique material name + texture set name -------------------------------
sub(
    '        self.terrain_materials: List[str] = ["grass"]',
    '        self.terrain_materials: List[str] = ["cs1_grass"]\n'
    '        # The TerrainMaterialTextureSet this level declares and its TerrainBlock references.\n'
    '        self.texture_set_name = f"{level_name}TerrainMaterialTextureSet"',
    "__init__ terrain_materials + texture_set_name",
)

# ---- 2. TerrainBlock must reference our own texture set --------------------------------
sub(
    '"materialTextureSet": "templateTerrainMaterialTextureSet",',
    '"materialTextureSet": self.texture_set_name,',
    "TerrainBlock materialTextureSet",
)

# ---- 3. keep 8192 out of the shipped envelope ------------------------------------------
sub(
    "def choose_terrain_size(extent: float) -> Tuple[int, float]:",
    "def choose_terrain_size(extent: float, max_resolution: int = 2048) -> Tuple[int, float]:",
    "choose_terrain_size max_resolution",
)
sub(
    """    for square_size in (1.0, 2.0, 4.0, 8.0, 16.0, 32.0):
        # +2 samples of margin so data never sits exactly on the border.
        needed = math.ceil(extent / square_size) + 2
        resolution = 128
        while resolution < needed:
            resolution *= 2
        if resolution <= 8192:
            return resolution, square_size

    return 8192, 64.0""",
    """    square_size = 1.0
    while True:
        needed = math.ceil(extent / square_size) + 2
        resolution = 128
        while resolution < needed and resolution < 8192:
            resolution *= 2
        resolution = min(resolution, 8192)

        if resolution <= max_resolution or square_size >= 128.0:
            return resolution, square_size

        square_size *= 2.0""",
    "choose_terrain_size body (grow squareSize, not the grid)",
)

# ---- 4. sub-group declarations must live in MissionGroup/items.level.json ---------------
sub(
    """        # Root: main/items.level.json declares the MissionGroup and its sub-groups.  A group
        # folder is only loaded when a SimGroup with that name is declared here.
        root_objects: List[Dict[str, Any]] = [
            {"class": "SimGroup", "name": "MissionGroup", "persistentId": new_id(), "enabled": "1"}
        ]
        for group in ("sky_and_sun",):
            root_objects.append(
                {"class": "SimGroup", "name": group, "persistentId": new_id(), "__parent": "MissionGroup"}
            )
        self.write_lines(os.path.join(self.main_root, "items.level.json"), root_objects)""",
    """        # Sub-groups live INSIDE the MissionGroup folder and each must be declared by a SimGroup
        # in MissionGroup/items.level.json.  The engine only walks into a sibling folder when the
        # parent file names a SimGroup matching it.  Roads and Buildings were once written but not
        # declared, so the level loaded with ZERO roads and ZERO buildings and no error at all.
        for group in ("sky_and_sun", "Roads", "Buildings"):
            if group == "Roads" and not self.roads:
                continue
            if group == "Buildings" and not self.buildings:
                continue
            objects.append(
                {"class": "SimGroup", "name": group, "persistentId": new_id(),
                 "__parent": "MissionGroup"}
            )

        self.write_lines(
            os.path.join(self.main_root, "MissionGroup", "items.level.json"), objects
        )

        # main/items.level.json declares only the top-level MissionGroup.
        root_objects: List[Dict[str, Any]] = [
            {"class": "SimGroup", "name": "MissionGroup", "persistentId": new_id(), "enabled": "1"}
        ]
        self.write_lines(os.path.join(self.main_root, "items.level.json"), root_objects)""",
    "sub-group declarations moved into MissionGroup file",
)

# ---- 5. buildings: two shapes + per-service material -----------------------------------
sub(
    '                "shapeName": f"/art/shapes/{self.mod_name}/cs1_proxy_box.dae",',
    '                "shapeName": f"/art/shapes/{self.mod_name}/cs1_building_{shape}.dae",',
    "building shapeName",
)
sub(
    '                "materialName": "cs1_proxy_building",',
    '                "materialName": building_material_name(building.service),',
    "building materialName",
)
sub(
    """            yaw = yaw_to_beamng(building.angle_radians)

            obj = {""",
    """            yaw = yaw_to_beamng(building.angle_radians)

            # Tall buildings get the stepped silhouette; everything else a block with a roof cap.
            shape = "tower" if height >= 24.0 and half_w < 22.0 else "block"

            obj = {""",
    "building shape selection",
)

# ---- 6. emit_proxy_box_shape -> emit the two generated shapes + materials --------------
OLD_SHAPE_START = "        dae_path = os.path.join(shape_dir, \"cs1_proxy_box.dae\")"
if OLD_SHAPE_START in s:
    # Replace from the dae_path line through the end of the old materials write_json call.
    start = s.index(OLD_SHAPE_START)
    marker = "self.write_json(os.path.join(shape_dir, \"main.materials.json\"), materials)"
    stop = s.index(marker, start) + len(marker)
    replacement = '''        for shape in ("block", "tower"):
            name = f"cs1_building_{shape}"
            dae_path = os.path.join(shape_dir, f"{name}.dae")
            with open(dae_path, "w", encoding="utf-8") as handle:
                handle.write(make_building_dae(name, shape))
            self.report["files"].append(os.path.relpath(dae_path, self.mod_root))

        self.write_json(
            os.path.join(shape_dir, "main.materials.json"), build_material_definitions()
        )'''
    s = s[:start] + replacement + s[stop:]
    print("  applied: emit_proxy_box_shape -> generated shapes + materials")

# ---- 7. docstring for that method ------------------------------------------------------
s = s.replace(
    """        One unit cube used by every building instance.

        The cube spans 0..1 in all axes and its origin is at the CENTRE of its X/Y footprint and
        at its BASE in Z, so an instance scale of (halfWidth, halfLength, height) plus a rotation
        about Z produces a box that stands on the terrain and is centred on the building.
        \"\"\"""",
    """        Generate the building shapes and their materials.

        Geometry spans X/Y in -0.5..0.5 (centred on the instance) and Z in 0..1 (base at Z=0), so
        an instance scale of (halfWidth, halfLength, height) plus a rotation about Z stands the
        mass on the terrain, centred on the building.

        The shapes carry no material binding on purpose, so each TSStatic's `materialName` decides
        the finish.  An earlier version bound a material inside the DAE; it did not resolve and
        every building rendered as the engine's flat orange warning material.
        \"\"\"""",
    1,
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(s)
print()
print("changed:", s != original)
