"""Emit terrain texture paths with forward slashes and the sanitised filenames."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = '''                # Keep the source form, including its backslash, but point at our copy.
                base = os.path.basename(value.replace("\\\\", "/"))
                if base in copied:
                    definition[field] = f"{vfs}\\\\{base}"
                else:
                    definition[field] = value'''

NEW = '''                # `copied` maps the source filename (which may contain '#' and is preceded by a
                # backslash in the source file) to a clean forward-slash path in this level.
                base = os.path.basename(value.replace("\\\\", "/"))
                if base in copied:
                    definition[field] = copied[base]
                else:
                    definition[field] = value'''

if OLD not in src:
    raise SystemExit("emitter anchor not found")
src = src.replace(OLD, NEW, 1)

# `vfs` is now unused for textures; leave the variable but note why.
src = src.replace(
    "        vfs = f\"/levels/{self.level_name.lower()}/art/terrains\"",
    "        # Texture paths come from copy_grille_terrain(), which already returns full paths with\n"
    "        # forward slashes and sanitised filenames.\n"
    "        vfs = f\"/levels/{self.level_name.lower()}/art/terrains\"",
    1,
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("uses copied[] paths :", "definition[field] = copied[base]" in src)
