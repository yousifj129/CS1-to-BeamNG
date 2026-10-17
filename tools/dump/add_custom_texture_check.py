"""
Add a conformance rule for the supplied ground texture.

`baseTexSize` declares a REQUIRED texture size and the engine discards anything that does not match
-- a rule that already cost several rounds here, when a 2048 declaration met 1024 textures and the
ground packed black.  A custom texture must be checked the same way, especially as it is now supplied
by hand rather than coming from the install.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

if "custom ground texture" in src:
    print("already present")
    raise SystemExit(0)

BLOCK = '''# ---------------------------------------------------------------- custom ground texture
# A level normally supplies its own large colour texture for the terrain base layer, and the engine
# ships no green terrain texture to substitute.  The converter now writes the supplied grass image
# into the level; this verifies it arrived at the size the texture set requires.  A mismatch is
# silent at build time and packs the layer black, so it is worth asserting.
if mat:
    required = None
    for _v in json.loads(z.read(mat_file[0]).decode("utf-8")).values():
        if _v.get("class") == "TerrainMaterialTextureSet":
            required = tuple(_v.get("baseTexSize") or ())
    declared = str(mat.get("baseColorBaseTex") or "")
    if declared.startswith("/levels/"):
        member = declared.lstrip("/")
        actual = None
        for _n in names:
            if _n.lower() == member.lower():
                actual = _n
                break
        check(actual is not None, "custom ground texture is present in the mod",
              declared)
        if actual is not None and required:
            head = z.read(actual)[:24]
            dim = struct.unpack(">II", head[16:24]) if head[:8] == b"\\x89PNG\\r\\n\\x1a\\n" else None
            check(dim == required,
                  "custom ground texture matches the declared baseTexSize",
                  f"texture {dim} vs declared {required}")
            # The whole point of shipping it: it must actually be green, unlike every engine terrain
            # texture, whose greenest measures a bias of only +15.
            if dim:
                import zlib as _zlib

                w_, h_ = dim
                blob = z.read(actual)
                off, raw = 8, bytearray()
                while off < len(blob):
                    ln = struct.unpack(">I", blob[off:off + 4])[0]
                    tag = blob[off + 4:off + 8]
                    if tag == b"IDAT":
                        raw += blob[off + 8:off + 8 + ln]
                    elif tag == b"IEND":
                        break
                    off += 12 + ln
                data = _zlib.decompress(bytes(raw))
                pitch = w_ * 3
                rows = []
                prev = bytearray(pitch)
                pos = 0
                for _y in range(h_):
                    ft = data[pos]
                    pos += 1
                    line = bytearray(data[pos:pos + pitch])
                    pos += pitch
                    if ft == 1:
                        for _i in range(3, pitch):
                            line[_i] = (line[_i] + line[_i - 3]) & 0xFF
                    elif ft == 2:
                        for _i in range(pitch):
                            line[_i] = (line[_i] + prev[_i]) & 0xFF
                    elif ft == 3:
                        for _i in range(pitch):
                            a = line[_i - 3] if _i >= 3 else 0
                            line[_i] = (line[_i] + ((a + prev[_i]) >> 1)) & 0xFF
                    elif ft == 4:
                        for _i in range(pitch):
                            a = line[_i - 3] if _i >= 3 else 0
                            bb = prev[_i]
                            cc = prev[_i - 3] if _i >= 3 else 0
                            p_ = a + bb - cc
                            pa, pb, pc = abs(p_ - a), abs(p_ - bb), abs(p_ - cc)
                            pr = a if (pa <= pb and pa <= pc) else (bb if pb <= pc else cc)
                            line[_i] = (line[_i] + pr) & 0xFF
                    rows.append(line)
                    prev = line
                tot = [0, 0, 0]
                cnt = 0
                for line in rows[::16]:
                    for _i in range(0, pitch - 2, 48):
                        tot[0] += line[_i]
                        tot[1] += line[_i + 1]
                        tot[2] += line[_i + 2]
                        cnt += 1
                if cnt:
                    rgb = tuple(t // cnt for t in tot)
                    bias = rgb[1] - (rgb[0] + rgb[2]) / 2.0
                    check(bias > 15.0,
                          "custom ground texture is genuinely green (bias > +15)",
                          f"mean RGB {rgb}, green bias {bias:+.1f}")

'''

anchor = "# ================================================================ lighting"
if anchor not in src:
    raise SystemExit("lighting anchor not found")
src = src.replace(anchor, BLOCK + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("added the custom-texture check; syntax OK")
