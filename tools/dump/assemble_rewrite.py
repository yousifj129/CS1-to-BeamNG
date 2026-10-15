"""Assemble the rewritten converter: preserved core + new emission layer + preserved tail."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
NEW_EMISSION = os.path.join(REPO, "build", "new_emission.py")

src = io.open(TARGET, encoding="utf-8").read()
lines = src.split("\n")

# Core: lines 1..1246 (module docstring, imports, value types, layout parsing, transforms,
# terrain reconstruction, .ter writer, PNG helpers).
core = "\n".join(lines[:1246])

emission = io.open(NEW_EMISSION, encoding="utf-8").read()

# Tail: the verification and CLI functions, which are correct and reusable.  They start at
# `_verify_ter_file` and run to the end of the file.
tail_start = next(
    i for i, l in enumerate(lines) if l.startswith("def _verify_ter_file(")
)
tail = "\n".join(lines[tail_start:])
print(f"core   : {len(core.split(chr(10)))} lines")
print(f"emission: {len(emission.split(chr(10)))} lines")
print(f"tail   : {len(tail.split(chr(10)))} lines")

combined = core + "\n" + emission + "\n\n" + tail

# The tail's verify_level carries checks written against the old layout; bring them in line.
combined = combined.replace(
    """        # The .ter is the terrain; a missing or malformed one is fatal.
""",
    """        # The .ter is the terrain; a missing or malformed one is fatal.
""",
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(combined)

try:
    ast.parse(combined)
    print("\nSYNTAX OK")
except SyntaxError as exc:
    print("\nSYNTAX ERROR line", exc.lineno)
    show = combined.split("\n")
    for i in range(max(0, exc.lineno - 4), min(len(show), exc.lineno + 3)):
        print(f"  {i + 1:>5}| {show[i][:110]}")
    raise SystemExit(1)

tree = ast.parse(combined)
names = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
print(f"total definitions: {len(names)}")
dupes = {n for n in names if names.count(n) > 1}
print("duplicates:", dupes or "NONE")
print(f"total lines: {len(combined.split(chr(10)))}")
