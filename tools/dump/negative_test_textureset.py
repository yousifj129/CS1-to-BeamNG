"""Negative test: removing the TerrainMaterialTextureSet must be detected."""

import json
import os
import shutil
import subprocess
import sys

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
SRC = os.path.join(REPO, "dist", "cs1_cannes")
DST = os.path.join(REPO, "build", "noset")

if os.path.isdir(DST):
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)

removed = []
for folder in ("terrains", "terrain"):
    path = os.path.join(DST, "levels", "Cannes", "art", folder, "main.materials.json")
    if not os.path.isfile(path):
        continue
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    data = {k: v for k, v in data.items() if v.get("class") != "TerrainMaterialTextureSet"}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    removed.append(path)

print("removed the texture set from:")
for path in removed:
    print("   ", os.path.relpath(path, REPO))

run = subprocess.run(
    [sys.executable, os.path.join(REPO, "tools", "verify_conversion.py"),
     os.path.join(REPO, "exports", "Cannes_city_layout.json"), "--mod", DST],
    capture_output=True, text=True,
)
print()
print("  exit:", run.returncode, "(1 = correctly detected)")
for line in run.stdout.splitlines():
    if line.strip().startswith("x "):
        print("   ", line.strip()[:120])

shutil.rmtree(DST, ignore_errors=True)
sys.exit(0 if run.returncode == 1 else 1)
