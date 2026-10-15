"""Make the terrain material build-unique and every declared size self-consistent at 1024."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- 1. unique material identity so the compiled-material cache cannot be reused ---------
old_name = '        self.terrain_materials: List[str] = [f"{level_name.lower()}_grass"]'
new_name = (
    "        # Include a random suffix in the name.  BeamNG caches compiled terrain materials by\n"
    "        # identity, and every variant tested produced the SAME cache key\n"
    "        # (/temp/art/terrainMaterialCache/CF2ACDF30CCC7F6C.dds) regardless of which textures or\n"
    "        # sizes were used.  A unique name per build makes a stale compiled entry impossible.\n"
    "        self.terrain_materials: List[str] = [\n"
    '            f"{level_name.lower()}_grass_{uuid.uuid4().hex[:8]}"\n'
    "        ]"
)
if old_name in src:
    src = src.replace(old_name, new_name, 1)
    print("  material name is now unique per build")
else:
    print("  material-name anchor missing; checking for the uuid version")
    print("  uuid version present:", "uuid.uuid4().hex[:8]" in src)

if "import uuid" not in src:
    src = src.replace("import struct\n", "import struct\nimport uuid\n", 1)
    print("  added: import uuid")

# ---- 2. declared sizes must match the textures the engine actually loads ----------------
old_size = """        # The working material declares *BaseTexSize 2048 while its detail/macro textures are
        # 1024, so the base size is independent of the others and is kept at 2048.
        base_size = 2048"""
new_size = """        # All three families use the engine's own 1024 textures, so every declared size is 1024.
        # A declared size that disagrees with the texture the engine loads is what stops the
        # texture array packing, and then every slot reports "Missing Terrain texture".
        base_size = 1024"""
if old_size in src:
    src = src.replace(old_size, new_size, 1)
    print("  base_size set to 1024 for consistency")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)

import ast

try:
    ast.parse(src)
    print("  SYNTAX OK")
except SyntaxError as exc:
    print("  SYNTAX ERROR line", exc.lineno)
    lines = src.split("\n")
    for i in range(max(0, exc.lineno - 3), min(len(lines), exc.lineno + 2)):
        print(f"    {i + 1:>5}| {lines[i]}")
    raise SystemExit(1)

print()
print("  uuid suffix  :", "uuid.uuid4().hex[:8]" in src)
print("  base_size    :", "base_size = 1024" in src)
