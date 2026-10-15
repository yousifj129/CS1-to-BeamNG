"""Prepare the repo for publishing: refresh the README's stale status, remove a duplicated comment."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"

# ---- 1. README status block -------------------------------------------------------------------
path = os.path.join(REPO, "README.md")
readme = io.open(path, encoding="utf-8").read()

old_status = """**Status:** Part 1 (the CS1 exporter) is implemented and compiles against the real game
assemblies. Part 2 (the BeamNG converter) has its data contract, validator and statistics
layer in place."""

new_status = """**Status:** both parts work end to end. The exporter is implemented and compiles against the real
game assemblies; the converter produces an installable BeamNG level from its output, and
`tools/dump/conformance.py` checks the result against measurements taken from a working map.

Maps produced so far are **playable and incomplete**. The road network, terrain and buildings are
present and drivable; the terrain's ground colour is approximate, and some building materials
inherited from the base game do not resolve (see "Known limitations" below)."""

if old_status not in readme:
    print("  note: the status block has already been updated or reworded")
else:
    readme = readme.replace(old_status, new_status, 1)
    print("  README status refreshed")

KNOWN = """
---

## Known limitations

Recorded because they are real and unresolved, not because they are being worked on immediately.

* **Ground colour is approximate.** A level normally ships its own large colour texture for the
  terrain's base layer. A converter cannot, and the engine ships no green *terrain* texture, so the
  greenest built-in set is used instead. Everything else about the ground -- tiling, detail, macro,
  normals, ground model -- is set from measured values.
* **Some base-game building materials do not resolve.** Materials declared inside another level's
  archive are not available when a shape is referenced from a different level, and the engine falls
  back to a warning material. Several are unresolved; the window materials have been defined.
* **`city_block3` and the other `west_coast_usa` building shapes are excluded** because their mesh
  origins sit hundreds of metres from their geometry, which makes them float when placed.
* **Terrain smoothness has one outlier.** The mean neighbour step is 2.6, but a single cell pair
  differs by a large amount -- one isolated cliff, about 0.0002% of cells.
* **`info.json` is written strictly**, while at least one shipped map ships a malformed one. No
  attempt is made to reproduce that.

## Repository layout

```
mod/       C# mod for Cities: Skylines 1 -- exports the city to JSON
tools/     Python converter, validator and conformance checker
docs/      Research notes, including a full technical reference for a working BeamNG map
exports/   Example city export
```

`docs/POLISH_ROADS_REFERENCE.md` is the most useful file here if you are building something similar.
It documents, from measurement rather than assumption, how a shipped BeamNG level is put together:
the `.ter` binary layout, terrain materials and their texture families, how ground physics is wired
through `groundmodelName`, the group and `__parent` rules for `items.level.json`, DecalRoad anatomy,
and lighting.

## A note on how this was built

Almost every difficult bug in this project was found by **measuring the built output**, not by
reading the code. The research notes record each one, including several where the first fix made
things worse and had to be reverted. If you extend this, the conformance checker
(`tools/dump/conformance.py`) is the thing that keeps those fixes from regressing -- it encodes the
rules learned the hard way, and it is worth running after every change.
"""

if "## Known limitations" not in readme:
    readme = readme.rstrip() + "\n" + KNOWN
    print("  README known-limitations and layout sections added")

io.open(path, "w", encoding="utf-8", newline="\n").write(readme)

# ---- 2. duplicated comment block in the converter ---------------------------------------------
tpath = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(tpath, encoding="utf-8").read()

first = """# Ground-plane centre offset of each shape's mesh, in the shape's own x/z, measured from its
# Collada POSITION accessors.  The mesh origin is a CORNER of the bounding box, not its centre:
# ind_bld_8x8 spans 8.2 m in -X and 0.1 m in +X from its origin.  Placing the TSStatic at the
# building's centre would therefore offset the whole mesh by half its width -- up to 30 m for
# ind_bld_24x60 -- which is why buildings interpenetrated and sat where they should not.
# Shapes whose measured size disagrees with the table by more than ~20% are omitted: their
# geometry carries node transforms this measurement does not apply (e.g. city_block3, which
# measures 6.3x its claimed size), so no offset is safer than a wrong one.

"""
if first in src:
    src = src.replace(first, "", 1)
    print("  removed the duplicated comment block")
else:
    print("  note: duplicated comment block not found verbatim")

io.open(tpath, "w", encoding="utf-8", newline="\n").write(src)

import ast

ast.parse(src)
print("  converter still parses")
