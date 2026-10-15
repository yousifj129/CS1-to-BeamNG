"""Restore the GROUND_MODELS block that an over-wide slice removed."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

if "GROUND_MODELS = {" in src:
    print("already present")
    raise SystemExit(0)

BLOCK = '''
# ==========================================================================================
#  Ground models -- physical surface behaviour
# ==========================================================================================
#
# Terrain friction is not set by the terrain material's textures: it is set by
# `TerrainMaterial.groundmodelName`, which is resolved against the engine's `/art/groundmodels.json`
# and then merged with any `levels/<level>/groundModels/*.json`.
#
# `groundmodelName` values this level uses are GRASS and ASPHALT.  Stock grass has low friction,
# which is why the whole map drove like loose gravel, so both are overridden at level scope.
#
# Values follow the documented meaning: `staticFrictionCoefficient` is grip before sliding,
# `slidingFrictionCoefficient` while sliding, and sliding is kept below static.
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

anchor = "def emit_ground_models(self) -> None:"
# Insert before the builder class instead, at module level.
anchor = "# ==========================================================================================\n#  Level builder"
if anchor not in src:
    raise SystemExit("level builder banner not found")
src = src.replace(anchor, BLOCK.strip() + "\n\n\n" + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("GROUND_MODELS restored:", "GROUND_MODELS = {" in src)
print("build_ground_models    :", "def build_ground_models(" in src)
