"""Append two late findings to the reference document: terrain tiling and global material scope."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 7c. Terrain tiling — `*TexSize` are metres per tile

The `*TexSize` fields are **the world size one texture tile covers, in metres**, not pixel
dimensions. That distinction caused real trouble: the terrain material was taken from
`east_coast_usa`, a large open-world map where a `baseColorBaseTexSize` of 2048 m is reasonable.
Applied to our 32.7 km terrain, one tile smeared across an enormous area and the ground read as
blocky, pixelated colour.

`macroDistances` and `detailDistances` are the distances at which the macro and detail families take
over from the base. Ours were `[0, 10, 100, 3000]` and `[0, 0, 30, 60]`, which kept the huge base
texture visible out to 3000 m.

Measured on this map: `baseColorBaseTexSize` 2048, `baseColorMacroTexSize` 80,
`baseColorDetailTexSize` 3. So Polish ships a 2048 m base tile, an 80 m macro tile and a 3 m detail
tile — a **ratio of roughly 680:27:1** across the three families.

Tuned values now in use, which tile finely enough for a 32.7 km map:

```
baseTexSize   256   (was 2048)
macroTexSize   32   (was   80)
detailTexSize   2   (was    4)
macroDistances   [0, 8, 40, 400]     (was [0, 10, 100, 3000])
detailDistances  [0, 0, 8, 20]       (was [0, 0, 30, 60])
```

## 7d. Material resolution scope — what is global and what is not

This is what causes the pale untextured "no material" window strips on buildings.

**A material declared inside a level resolves only for that level.** Several base-game building
shapes declare window materials in *italy's* archive:

```
Italy_bld_ind_windows   (5 of the 8 shapes we reference)
italy_bld_windows       (2 shapes)
windows_doors_reflective (3 shapes)
```

Referenced from another level, the first two do not resolve.

**But `content/art_shapes.zip` is mounted globally**, and it holds **39 material libraries**,
including:

```
art/shapes/objects/m_windows_glass_01/main.materials.json          lit windows, emissive
art/shapes/objects/m_transparent_glass_window/main.materials.json  clear-coated glass
art/shapes/objects/windows_doors_reflective/main.materials.json    reflective glazing
```

So `windows_doors_reflective` resolves on its own and must **not** be aliased — pointing it at plain
glass would replace a working reflective material with a worse one.

The fix for the other two is an alias, which authors nothing:

```json
{ "Italy_bld_ind_windows": { "name": "Italy_bld_ind_windows", "mapTo": "m_windows_glass_01", "class": "Material" },
  "italy_bld_windows":     { "name": "italy_bld_windows",     "mapTo": "m_windows_glass_01", "class": "Material" } }
```

`mapTo` redirects the name the shape asks for to a material the engine already has. No stages, no
parameters, no new material.

**The general rule, worth stating plainly:** before authoring a material, search the engine's
archives for it. `art_shapes.zip` and the `content/assets/materials/*.zip` set are mounted for every
level, and between them they already define most of what a converted city needs. Our converter's
first window-alias attempt used thirteen *guessed* names; reading the shapes'
`<library_materials>` blocks showed only two were real.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended sections 7c and 7d")
print("document is now", len(text.split("\n")), "lines")
