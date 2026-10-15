"""
Use the MEASURED window material names as aliases.

The first version of this list was guessed, and almost every name in it was wrong.  Reading the
`<library_materials>` block of the eight building shapes we actually reference gives the real
names.  Across those shapes the glazing materials are:

    Italy_bld_ind_windows     (5 shapes)
    italy_bld_windows         (2 shapes)
    windows_doors_reflective  (3 shapes)

The first two live in `levels/italy/art/terrains/main.materials.json` -- i.e. inside italy's own
archive -- so they do not resolve when the shape is referenced from another level.  That is the
pale untextured strip in the screenshots.

`windows_doors_reflective` is different: it is defined in `content/art_shapes.zip` as global
content, alongside 38 other material libraries, so the engine already resolves it.  It is therefore
NOT aliased -- forcing it to glass would replace a working reflective material with a worse one.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("BUILDING_WINDOW_ALIASES = [")
end = src.index("]", start) + 1

NEW_LIST = '''BUILDING_WINDOW_ALIASES = [
    # Measured from the <library_materials> block of the eight base-game building shapes this
    # converter references.  These two are declared inside italy's own archive and therefore do
    # not resolve from another level -- they are the untextured window strips.
    "Italy_bld_ind_windows",
    "italy_bld_windows",
    # `windows_doors_reflective` is deliberately NOT listed: the engine already defines it in
    # content/art_shapes.zip as global content, so it resolves on its own.  Aliasing it would
    # replace a working reflective material with plain glass.
]'''

src = src[:start] + NEW_LIST + src[end:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("aliases now:", src[src.index("BUILDING_WINDOW_ALIASES"):src.index("]", src.index("BUILDING_WINDOW_ALIASES")) + 1])
