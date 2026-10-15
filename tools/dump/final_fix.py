"""Final touch-up: remove the duplicated make_terrain_texture and restore build()."""

import collections
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
bak = io.open(os.path.join(REPO, "build", "beamng_convert.py.bak"), encoding="utf-8").read().split("\n")
lines = io.open(TARGET, encoding="utf-8").read().split("\n")


def end_of_block(lines, start):
    """Index just past a top-level def block (next line that starts at column 0 and is not blank)."""
    for i in range(start + 1, len(lines)):
        if lines[i].strip() and not lines[i].startswith((" ", "\t")):
            return i
    return len(lines)


# ---- 1. drop the second make_terrain_texture -------------------------------------------
hits = [i for i, l in enumerate(lines) if l.startswith("def make_terrain_texture(")]
print("make_terrain_texture at:", [i + 1 for i in hits])
if len(hits) == 2:
    start, stop = hits[1], end_of_block(lines, hits[1])
    while stop - 1 > start and lines[stop - 1].strip() == "":
        stop -= 1
    print(f"  removing duplicate lines {start + 1}..{stop}")
    lines = lines[:start] + lines[stop:]

# ---- 2. restore build() from the backup -------------------------------------------------
if not any(l.strip().startswith("def build(self)") for l in lines):
    b_start = next(i for i, l in enumerate(bak) if l.strip().startswith("def build(self) -> None:"))
    b_end = next(i for i, l in enumerate(bak) if l.startswith("def zip_mod("))
    block = bak[b_start:b_end]
    while block and block[-1].strip() == "":
        block.pop()
    print(f"inserting build() ({len(block)} lines) from the backup")
    # Append as the final method of the class: find where the class ends (first top-level def
    # after `class BeamNGLevelBuilder`).
    cls = next(i for i, l in enumerate(lines) if l.startswith("class BeamNGLevelBuilder"))
    after = next(i for i in range(cls + 1, len(lines)) if lines[i].startswith("def "))
    lines = lines[:after] + block + [""] + lines[after:]

text = "\n".join(lines)

# build() must call the new preview emitter.
if "self.emit_preview_image()" not in text:
    text = text.replace(
        "        self.emit_terrain_files()\n        self.emit_info_json()",
        "        self.emit_terrain_files()\n        self.emit_preview_image()\n        self.emit_info_json()",
    )

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(text)

final = text.split("\n")
tops = collections.Counter(l for l in final if l.startswith(("class ", "def ")))
dups = {k: v for k, v in tops.items() if v > 1}
print()
print(f"final: {len(final)} lines")
print(f"duplicates: {dups if dups else 'NONE'}")
for want in ("def build(self)", "def emit_preview_image(self)", "def emit_terrain_materials(self)",
             "def emit_sky_and_sun(self)", "def make_terrain_texture", "def zip_mod"):
    print(f"  {want:<34} x{text.count(want)}")
print(f"  build() calls emit_preview_image: {'self.emit_preview_image()' in text}")
