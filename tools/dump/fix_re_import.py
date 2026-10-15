"""Add `import re` where missing and relax the converter's own cross-level shape check."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"

for rel in ("tools/verify_conversion.py", "tools/beamng_convert.py"):
    path = os.path.join(REPO, rel)
    src = io.open(path, encoding="utf-8").read()
    lines = src.split("\n")
    if any(l.strip() == "import re" for l in lines):
        print(f"  {rel}: re already imported")
    else:
        for i, l in enumerate(lines):
            if l.strip() == "import os":
                lines.insert(i + 1, "import re")
                break
        else:
            raise SystemExit(f"no `import os` anchor in {rel}")
        src = "\n".join(lines)
        io.open(path, "w", encoding="utf-8", newline="\n").write(src)
        print(f"  {rel}: added import re")

# The converter has its own verify_level with the same shape-existence test.
conv = io.open(os.path.join(REPO, "tools/beamng_convert.py"), encoding="utf-8").read()
print()
print("converter shape checks:")
for i, l in enumerate(conv.split("\n"), 1):
    if "missing shape" in l or ("shapeName" in l and "get" in l) or "shape_path" in l:
        print(f"  {i}: {l.strip()}")
