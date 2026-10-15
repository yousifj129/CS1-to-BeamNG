"""
Fix `_smooth`, which silently changed the array shape on every call.

The vertical pass padded `horizontal` and then sliced COLUMNS instead of ROWS:

    np.pad(horizontal, 1, mode="edge")[0:-2, :]     <- cuts rows, keeps the padded width

`horizontal` is already h x w, so padding makes it (h+2, w+2) and `[0:-2, :]` leaves (h, w+2).
The result therefore had the right height and **two extra columns**, and two extra rows lost.

This never showed up because every caller fed the result into `_as_square`, which crops it back --
so the shape damage was silently repaired and the only visible effect was a slight smearing along
one edge.  It surfaced now only because the new coarse smoothing blends two grids together, and a
(2048,2054) array cannot be added to a (2048,2048) one.

The fix indexes ROWS, using the already-correct size of `horizontal` rather than re-padding it.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = """        horizontal = (
            padded[1:-1, :-2] + padded[1:-1, 1:-1] + padded[1:-1, 2:]
        ) / 3.0
        vertical = (
            np.pad(horizontal, 1, mode="edge")[0:-2, :]
            + np.pad(horizontal, 1, mode="edge")[1:-1, :]
            + np.pad(horizontal, 1, mode="edge")[2:, :]
        ) / 3.0

        result = vertical"""

NEW = """        horizontal = (
            padded[1:-1, :-2] + padded[1:-1, 1:-1] + padded[1:-1, 2:]
        ) / 3.0

        # `horizontal` is already h x w, so the vertical pass indexes ROWS directly.  The previous
        # version padded it and sliced `[0:-2, :]`, which cuts rows but keeps the padded width --
        # returning (h, w+2) and dropping two rows.  `_as_square` hid the damage at every call site.
        vertical = (
            horizontal[:-2, :] + horizontal[1:-1, :] + horizontal[2:, :]
        ) / 3.0

        result = vertical"""

if OLD not in src:
    raise SystemExit("_smooth body anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("_smooth fixed:", "horizontal[:-2, :] + horizontal[1:-1, :] + horizontal[2:, :]" in src)
