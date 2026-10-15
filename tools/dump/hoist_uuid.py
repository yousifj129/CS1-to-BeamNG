"""Hoist `import uuid` to module scope so the terrain material name can use it."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

if "\nimport uuid\n" not in src:
    src = src.replace("import unicodedata\n", "import unicodedata\nimport uuid\n", 1)
    print("hoisted import uuid to module scope")
else:
    print("already at module scope")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")

# Confirm it is importable in isolation.
import subprocess
import sys

proc = subprocess.run(
    [sys.executable, "-c", "import ast,io;src=io.open(r'%s',encoding='utf-8').read();"
     "tree=ast.parse(src);"
     "print('module-level import uuid:', any(isinstance(n, ast.Import) and "
     "any(a.name=='uuid' for a in n.names) for n in tree.body))" % TARGET],
    capture_output=True, text=True,
)
print(proc.stdout.strip() or proc.stderr.strip())
