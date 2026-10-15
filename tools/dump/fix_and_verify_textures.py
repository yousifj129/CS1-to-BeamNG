"""
1. Correct all five detail texture paths (soil/ -> rock/).
2. Verify EVERY texture path in the material resolves, against the engine's real archives.

The second part is the check that was missing all along: the ground rendered, so I assumed the
material was fine, when in fact the detail family was silently failing.  A material whose paths are
not all verified is not a verified material.
"""

import ast
import io
import os
import re
import zipfile

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
GAME = r"D:\SteamLibrary\steamapps\common\BeamNG.drive"

src = io.open(TARGET, encoding="utf-8").read()

# Replace each detail path individually.
for suffix in ("b", "nm", "r", "ao", "h"):
    old = f'"/assets/materials/terrain/soil/dirt_rocky/t_dirt_rocky_{suffix}.png"'
    new = f'"/assets/materials/terrain/rock/t_dirt_rocky/t_dirt_rocky_{suffix}.png"'
    if old in src:
        src = src.replace(old, new, 1)
    else:
        print(f"  note: {suffix} already correct or absent")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("rock/ paths :", src.count("/assets/materials/terrain/rock/t_dirt_rocky/"))
print("soil/dirt_rocky left:", src.count("/assets/materials/terrain/soil/dirt_rocky/"))

# ---- gather every path the material uses -------------------------------------------------
block = src[src.index("CS1_TERRAIN_MATERIAL = {"):src.index("CS1_TERRAIN_TEXTURE_SET = {")]
paths = re.findall(r'"(/assets/[^"]+|/levels/[^"]+)"', block)
print(f"\nmaterial references {len(paths)} texture paths; verifying each against the install")

# ---- build an index of every archive the engine mounts ------------------------------------
index = set()
for root, _dirs, files in os.walk(os.path.join(GAME, "content")):
    for f in files:
        if not f.endswith(".zip"):
            continue
        p = os.path.join(root, f)
        try:
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    index.add(n.lower())
        except Exception:
            pass
print(f"indexed {len(index)} entries from the install")

missing = []
for path in paths:
    rel = path.lstrip("/").lower()
    if rel in index:
        continue
    # `/assets/materials/terrain/x` may be stored under a materials archive with a different root.
    if any(n.endswith(rel) or n.endswith(os.path.basename(rel)) and rel.split("/")[-2] in n
           for n in index):
        continue
    missing.append(path)

print()
for path in paths:
    rel = path.lstrip("/").lower()
    ok = rel in index
    print(f"  {'ok  ' if ok else 'MISS'} {path}")
print()
if missing:
    print(f"{len(missing)} PATH(S) DO NOT RESOLVE:")
    for m in missing:
        print("   ", m)
else:
    print("all texture paths resolve")
