"""Document the texture-rendering lesson and the reference grass structure."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 19. Red grass: the mean of a texture does not describe its appearance

Three rounds of grass "fixes" went wrong for one reason: the choice was made by **averaging** texture
pixels, which cannot distinguish a green texture from a red one that happens to have a similar mean.

Rendering the three textures the material actually used made the cause immediate:

| family | texture | what it actually is |
|---|---|---|
| BASE | `forest/t_forest_ground_02` | green -- yellow-green grass with pale stone flecks |
| DETAIL | `grass/t_grass_02` | green/olive, fine |
| MACRO | `forest/t_macro_forest` | **RED / brown** |

`t_macro_forest` averages `(110, 110, 110)` -- which the mean-based scan read as neutral -- but its
pixels are red-brown. Worse, it was tiled at **1 metre**, so it repeated 1024 times and dominated
everything under the camera. That is precisely the reported symptom: red from above, dark mud close
up. The green base was buried underneath.

The contact sheets are written to `build/texture_sheet.png` and `build/current_stack.png`; the
generator is `tools/dump/make_texture_sheet.py`. **Look at a texture before choosing it.**

## 20. The reference grass structure, and why the tile sizes were backwards

polish_roads_v2's `Grass`, field for field:

```
baseColorBaseTex          local t_terrain_base_b      size 2048
baseColorDetailTex        t_grass_01_b                size 3
baseColorMacroTex         t_macro_grass_b             size 80
baseColorDetailStrength   [0.4, 0.45]
baseColorMacroStrength    [0, 0.1]
detailDistances           [0, 0, 50, 80]
macroDistances            [0, 0, 400, 8000]
detailSize 4   macroSize 50   detailDistance 25   macroDistance 1000
detailDistAtten [0, 1]   macroDistAtten [0.35, 1]
```

The shape of it:

* the **base** carries the colour and is **large** -- 2048 m in the reference -- stretched so that no
  repeat is visible. It is the stand-in for a level's own colour texture.
* the **detail** is **small** (3 m) and subtle, adding fine variation near the camera.
* the **macro** is **large** (80 m) and very subtle, adding large-scale variation.

Everything here had been set to 0.5-4 m for all three families, which is the opposite: it made every
layer repeat visibly, and it let the red macro dominate.

Current values, which follow the reference's shape scaled for a 32 km world:

| family | texture | tile | role |
|---|---|---|---|
| base | `forest/t_forest_ground_02` | **200 m** | the colour -- green |
| detail | `grass/t_grass_01` | **4 m** | fine variation |
| macro | `grass/macro_grass` | **60 m** | large-scale variation |

The engine ships no green *terrain* texture other than the forest ground sets -- a scan of every
material archive found only four textures with any green bias, and `t_forest_ground_02` at
`(121, 124, 97)` is the only strong one. A level supplies its own colour texture for this slot; a
converter cannot, so the greenest built-in texture is used with the tile sizes set so its small red
flecks read as ground detail rather than as the ground colour.

Three conformance rules now encode the reference's shape rather than the earlier wrong assumption:
the base must be >= 64 m, the detail 1-12 m, the macro >= 32 m, and base and detail must not be the
same file (an identical pair applies one map twice, which was a real defect here).

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended sections 19-20; document is now", len(text.split("\n")), "lines")
