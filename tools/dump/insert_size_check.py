"""Insert the texture-size check using an anchor that exists."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

if "every base texture matches the declared baseTexSize" in src:
    print("already present")
    raise SystemExit(0)

BLOCK = '''# ---------------------------------------------------------------- texture pixel sizes
# `baseTexSize` is a REQUIRED pixel size.  A texture whose real size differs is discarded and the
# layer packs black, so a path resolving is not enough -- the size must match too.  This is the
# check whose absence cost several rounds.
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

    data2 = json.loads(z.read(mat_file[0]).decode("utf-8"))
    required = None
    for v in data2.values():
        if v.get("class") == "TerrainMaterialTextureSet":
            required = tuple(v.get("baseTexSize") or ())
    base_mats = [v for v in data2.values() if v.get("class") == "TerrainMaterial"]

    if required:
        wrong, missing = [], []
        for m in base_mats:
            for key, value in m.items():
                if key.endswith("BaseTex") and isinstance(value, str) and value.startswith("/"):
                    dim = dims.get(value.lower())
                    if dim is None:
                        missing.append(value)
                    elif dim != required:
                        wrong.append(f"{os.path.basename(value)}={dim}")
        check(not missing, "every base texture resolves in the install", f"{len(missing)} missing")
        check(
            not wrong,
            "every base texture matches the declared baseTexSize",
            f"baseTexSize={required}"
            + (f"; mismatches: {wrong[:4]}" if wrong else "; all match"),
        )

'''

anchor = "# ---------------------------------------------------------------- painted road surface"
if anchor not in src:
    raise SystemExit("painted road surface anchor not found")
src = src.replace(anchor, BLOCK + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("inserted the texture-size check; syntax OK")
