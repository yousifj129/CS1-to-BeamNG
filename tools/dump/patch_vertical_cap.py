"""Cap the vertical stretch of building models."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = """        # Uniform in X and Y; Z follows the same factor so the model is not squashed vertically,
        # except that very tall CS1 buildings are allowed to stretch modestly.
        (uniform, uniform, max(uniform, min(vertical, uniform * 2.5))),"""
NEW = """        # Uniform in X and Y, so the mesh keeps its proportions.  Z follows the same factor with
        # a ceiling: CS1 heights are genuine, but stretching a model 2.6x vertically is as
        # disfiguring as squashing it sideways, so a tall building is allowed to fall short rather
        # than deform.  For a drivable map, footprint fidelity matters more than exact height.
        (uniform, uniform, max(uniform, min(vertical, uniform * 1.6))),"""

if OLD not in src:
    raise SystemExit("vertical scale anchor not found")
src = src.replace(OLD, NEW, 1)
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("vertical cap now 1.6x:", "uniform * 1.6" in src)
