"""
Add level ground models, which is what actually controls road grip.

Friction on terrain comes from `TerrainMaterial.groundmodelName`, resolved against
`/art/groundmodels.json` and then merged with any `levels/<level>/groundModels/*.json`.  This level
declares one, giving the asphalt and grass surfaces the coefficients the request asks for.

Grip is deliberately raised above stock grass values, because the whole terrain currently uses the
single grass material -- there is no separate asphalt surface yet, so the material under the wheels
is grass even where a road decal is drawn.  A DecalRoad in BeamNG is a decal: it changes how the
ground looks, not what the tyres grip.  Making the grass model behave like a firm, grippy surface
is therefore the correct fix for the slipperiness at this stage.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

GROUND_MODELS = '''

# ==========================================================================================
#  Ground models -- physical surface behaviour
# ==========================================================================================
#
# Terrain friction is not set by the terrain material's textures: it is set by
# `TerrainMaterial.groundmodelName`, which is resolved against the engine's `/art/groundmodels.json`
# and then merged with any `levels/<level>/groundModels/*.json`.
#
# The single terrain material this level ships uses `groundmodelName: "GRASS"`, and stock grass has
# low friction, which is why the surface drove like loose gravel.  Overriding the two models below
# at level scope raises it.
#
#   GRASS    deliberately firm: this is the surface under the wheels everywhere, including beneath
#            road decals, because a DecalRoad is only a decal -- it changes appearance, not grip.
#   ASPHALT  declared for completeness, so a future road surface material has a target.
#
# Values follow the documented meaning: staticFrictionCoefficient is grip before sliding,
# slidingFrictionCoefficient while sliding, and sliding is kept below static.
GROUND_MODELS = {
    "grass": {
        "staticFrictionCoefficient": 0.95,
        "slidingFrictionCoefficient": 0.85,
        "roughnessCoefficient": 0.02,
        "hydrodynamicFriction": 0.005,
        "strength": 1.0,
        "collisiontype": "GRASS",
        "skidMarks": False,
        "defaultDepth": 0.0,
        "shearStrength": 0.0,
    },
    "asphalt": {
        "staticFrictionCoefficient": 1.10,
        "slidingFrictionCoefficient": 1.00,
        "roughnessCoefficient": 0.0,
        "hydrodynamicFriction": 0.01,
        "strength": 1.0,
        "collisiontype": "ASPHALT",
        "skidMarks": True,
        "defaultDepth": 0.0,
        "shearStrength": 0.0,
    },
}


def build_ground_models() -> Dict[str, Any]:
    """The level's `groundModels/*.json` payload."""
    return {name: dict(body) for name, body in GROUND_MODELS.items()}
'''

anchor = "def build_window_material_aliases() -> Dict[str, Any]:"
if anchor not in src:
    raise SystemExit("window alias function anchor not found")
src = src.replace(anchor, GROUND_MODELS.strip() + "\n\n\n" + anchor, 1)

# ---- emitter ------------------------------------------------------------------------------
METHOD = '''    def emit_ground_models(self) -> None:
        """
        Write `levels/<level>/groundModels/surfaces.json`.

        The engine merges this over `/art/groundmodels.json` at level load, so declaring a name
        the common file already defines overrides it for this level only.
        """
        path = os.path.join(self.level_root, "groundModels", "surfaces.json")
        models = build_ground_models()
        self.write_json(path, models)
        self.report["groundModels"] = sorted(models)

'''
anchor2 = "    def emit_building_materials(self) -> None:"
if anchor2 not in src:
    raise SystemExit("building materials emitter anchor not found")
src = src.replace(anchor2, METHOD + anchor2, 1)

# ---- call it ------------------------------------------------------------------------------
OLD_CALL = """        self.emit_sky_and_sun()
        self.emit_spawns_and_mission()"""
NEW_CALL = """        self.emit_ground_models()
        self.emit_sky_and_sun()
        self.emit_spawns_and_mission()"""
if OLD_CALL not in src:
    raise SystemExit("build call anchor not found")
src = src.replace(OLD_CALL, NEW_CALL, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("ground models defined :", "GROUND_MODELS = {" in src)
print("emitter defined       :", "def emit_ground_models(" in src)
print("emitter called        :", "self.emit_ground_models()" in src)
