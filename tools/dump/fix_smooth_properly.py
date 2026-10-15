"""
Fix `_smooth` properly, with an explicit shape check.

Two previous attempts got the indexing wrong.  The pass is a separable box blur:

    horizontal : 3-wide average across columns -> h x w
    vertical   : 3-tall average across rows    -> h x w

For the vertical step the array must first be padded by one ROW at top and bottom while keeping w
columns.  Writing it explicitly and asserting the output shape removes the room for off-by-one
errors that produced (h-2, w) and (h, w+2) in earlier attempts.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("def _smooth(")
end = src.index("\ndef ", start + 1)

NEW = '''def _smooth(grid: Any, iterations: int = 1) -> Any:
    """
    Separable 3x3 box blur, with edge clamping (not wraparound) so map borders do not smear across
    from the opposite side.  The output always has exactly the same shape as the input.

    Both passes are written explicitly rather than chained through `np.pad` results, because two
    earlier versions sliced the wrong axis after padding and returned (h-2, w) or (h, w+2).  The
    shape damage was invisible while every caller fed the result through `_as_square`, which crops
    silently; it only became a hard error once two grids of different shapes were blended.
    """
    result = grid.astype(np.float32)

    for _ in range(iterations):
        # Horizontal: average along the column axis, padding width by one on each side.
        padded = np.pad(result, ((0, 0), (1, 1)), mode="edge")
        horizontal = (
            padded[:, :-2] + padded[:, 1:-1] + padded[:, 2:]
        ) / 3.0

        # Vertical: average along the row axis, padding height by one on each side.
        padded = np.pad(horizontal, ((1, 1), (0, 0)), mode="edge")
        result = (
            padded[:-2, :] + padded[1:-1, :] + padded[2:, :]
        ) / 3.0

    return result
'''

src = src[:start] + NEW + src[end + 1 :]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")

import sys

sys.path.insert(0, os.path.join(REPO, "tools"))
import numpy as np

import beamng_convert as B

ok = True
for shape in ((2048, 2048), (512, 512), (100, 100), (7, 9), (3, 3), (1, 1)):
    g = np.random.rand(*shape).astype(np.float32)
    r = B._smooth(g, iterations=3)
    good = r.shape == shape
    ok = ok and good
    print(f"  in {str(shape):<14} -> out {str(r.shape):<14} {'OK' if good else 'WRONG'}")
print()
print("all shapes preserved:", ok)
