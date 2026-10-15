"""
Add a texture-size conformance check, then rebuild.

This is the check whose absence cost several rounds: the declared `baseTexSize` was 2048 while every
texture was 1024, so the engine rejected all of them and packed a black layer.  Verifying that paths
RESOLVE is not enough -- the size has to match too.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

BLOCK = '''
# ---------------------------------------------------------------- texture sizes
# `baseTexSize` is a REQUIRED pixel size.  A texture whose real size differs is discarded and the
# layer packs black, so paths resolving is not sufficient -- the size must match too.
GAME = r"D:\\SteamLibrary\\steamapps\\common\\BeamNG.drive"
if mat_file and os.path.isdir(GAME):
    dims = {}
    for root, _dirs, files in os.walk(os.path.join(GAME, "content")):
        for fname in files:
            if not fname.endswith(".zip"):
                continue
            try:
                archive = zipfile.ZipFile(os.path.join(root, fname))
            except Exception:
                continue
            for info in archive.infolist():
                if not info.filename.lower().endswith(".png"):
                    continue
                try:
                    head = archive.read(info.filename)[:24]
                except Exception:
                    continue
                if head[:8] == b"\\x89PNG\\r\\n\\x1a\\n":
                    dims["/" + info.filename.lower()] = struct.unpack(">II", head[16:24])
            archive.close()

    data = json.loads(z.read(mat_file[0]).decode("utf-8"))
    required = None
    for v in data.values():
        if v.get("class") == "TerrainMaterialTextureSet":
            required = tuple(v.get("baseTexSize") or ())
    mats = [v for v in data.values() if v.get("class") == "TerrainMaterial"]

    if required:
        wrong, missing = [], []
        for m in mats:
            for key, value in m.items():
                if not isinstance(value, str) or not value.startswith("/"):
                    continue
                if not key.endswith("BaseTex"):
                    continue
                dim = dims.get(value.lower())
                if dim is None:
                    missing.append(value)
                elif dim != required:
                    wrong.append(f"{os.path.basename(value)} {dim} != {required}")
        check(not missing, "every base texture resolves in the install", f"{len(missing)} missing")
        check(
            not wrong,
            "every base texture matches the declared baseTexSize",
            f"baseTexSize={required}; mismatches: {wrong[:4]}" if wrong else f"baseTexSize={required}",
        )
'''

anchor = "# ---------------------------------------------------------------- lighting"
if anchor not in src:
    raise SystemExit("lighting section anchor not found")
src = src.replace(anchor, BLOCK.strip() + "\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("added the texture-size check; syntax OK")
