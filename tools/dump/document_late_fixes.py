"""Record the two late defects in the reference document."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 7e. Two defects that only the log could reveal

Both of these produced a level that *looked* partly right, which is why they survived several
rounds of static checking.

### A texture path that was one directory wrong

Once the `.ter` was correct the ground rendered, so the material appeared to be working. It was not:
the log then began naming the resources it could not find.

```
E|TerrainCellMaterial| Missing Terrain texture: /assets/materials/terrain/soil/dirt_rocky/t_dirt_rocky_r.png
```

Those five files do not exist under `soil/`. They are under `rock/`:

```
assets/materials/terrain/rock/t_dirt_rocky/t_dirt_rocky_{b,nm,r,ao,h}.png
```

The base family loaded and the **detail family silently did not**, so the ground showed the large
base tile with no fine detail -- which reads exactly as "the texture is too big". The material had
been copied from `east_coast_usa`, and the path was wrong from the start.

**Lesson:** a material whose texture paths have not each been verified against the install is not a
verified material. The converter now checks all fifteen, and the check is in the conformance report.

### Aliases written to a path the engine does not read

The window-material aliases were written to `levels/Cannes/main.materials.json` and
`art/shapes/<mod>/main.materials.json`. Neither is a path this engine loads for a level, so the
aliases had **no effect whatsoever**.

The one material library proven to load for a level is
`levels/<level>/art/terrains/main.materials.json` -- proven because the terrain material resolves
from it and the ground renders. The aliases are now merged into that same file as additional
top-level keys. If the engine loads it for the terrain, it registers them.

**Lesson:** write material definitions only where the engine demonstrably loads them from. "A file
with the right name in a plausible place" is not evidence of anything.

### Tiling, corrected

With the detail family actually loading, the tile sizes were still far too coarse. `*TexSize` is
metres per tile, so at 1024x1024 a 256 m tile is 25 cm per texel -- visibly blocky.

| Family | Polish | Ours (now) | Texel size at 1024 px |
|---|---|---|---|
| base | 2048 m | **10 m** | 9.8 mm |
| macro | 80 m | **4 m** | 3.9 mm |
| detail | 3 m | **2 m** | 2.0 mm |

Polish can use a 2048 m base tile because its world is about 2 km across. Ours spans 32.7 km, so
the same value smears one texture over sixteen times the area. Tile sizes have to be chosen for the
map's own scale, not copied from a map of a different size.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 7e")
print("document is now", len(text.split("\n")), "lines")
