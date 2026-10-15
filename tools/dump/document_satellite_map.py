"""Record the satellite-map discovery in the reference document."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 7f. The base terrain texture was a satellite map, not a texture

The single most misleading asset in this whole exercise.

`t_terrain_base_b.png` in `levels/east_coast_usa/art/terrains/` is **a top-down satellite image of
that level** -- you can see its roads, field boundaries and riverbeds -- and it is **not tileable**.
Repeating it drew a visible grid of maps across the ground, which reads as "the tile is too big"
even when the tile size is small. The screenshots show the grid seams plainly.

It is one of a five-file base family (`_b`, `_nm`, `_r`, `_ao`, `_h`) that a working level ships
under `art/terrains/`, and it is intended to be stretched **once** across that level's whole
terrain as a large-scale colour wash. It is not a surface texture and cannot be tiled.

### What to use instead

The engine ships genuinely seamless grass sets in `content/assets/materials/terrain.zip`, each a
complete 1024x1024 family:

| Set | Path |
|---|---|
| `t_grass_01` | `grass/t_grass_01/t_grass_01_{b,nm,r,ao,h}.png` |
| `t_grass_02` | `grass/t_grass_02/t_grass_02_{b,nm,r,ao,h}.png` |
| `ind_grass` | `grass/ind_grass/t_ind_grass_{b,nm,r,ao,h}.png` |
| `macro_grass` | `grass/macro_grass/t_macro_grass_{b,nm,r,ao,h}.png` |

Three are used, one per scale, so the three families do not repeat in step with each other:

```
base    t_grass_02      the ground colour
macro   t_macro_grass   large-scale variation, breaks up the repeat
detail  ind_grass       fine detail near the camera
```

### Tiling for map scale, not copied from another map

| | This map | Ours (final) |
|---|---|---|
| base | 2048 m | **8 m** |
| macro | 80 m | **2 m** |
| detail | 3 m | **0.5 m** |

Polish uses a 2048 m base tile because its world is about 2 km across and it *wants* the satellite
wash stretched over the whole thing. Ours spans 32.7 km, so a tile of that size covers a sixteenth
of the map. Tile sizes have to be chosen for the map's own extent.

### The general rule this keeps teaching

Three separate rounds were lost to the same mistake in different clothes:

1. a `.ter` field (`layerTextureMap`) invented from a descriptive string that was itself wrong;
2. a texture path (`soil/` vs `rock/`) assumed rather than checked;
3. a texture (`t_terrain_base_b`) assumed to be a surface texture because of its name.

**Look at what the asset actually is, and confirm the path resolves, before using it.** Both checks
are now in the conformance report: all fifteen paths are verified against the install, and the base
textures are asserted not to be `t_terrain_base*`.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 7f; document is now", len(text.split("\n")), "lines")
