"""Document the green texture search and the tower removal."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 16. The green texture, found by scanning everything

Sections 15.1-15.2 concluded that no engine terrain texture is green. That was **too narrow**: the
scan had only looked at `terrain.zip`. Scanning every texture archive in the install for a green bias
(`G - (R+B)/2`) found exactly **four** green-ish textures in the whole game:

| texture | mean RGB | green bias |
|---|---|---|
| `terrain/forest/t_forest_ground_02/t_forest_ground_02_b.png` | 121, 124, 97 | **+15.0** |
| `terrain/forest/t_forest_ground_02/t_forest_ground_03_b.png` | 113, 111, 95 | +7.0 |
| `terrain/asphalt/m_asphalt/t_terrain_base_asphalt_b.png` | 118, 115, 102 | +5.0 |
| `terrain/grass/t_macro_dry_grass/t_macro_dry_grass_02_b.png` | 117, 115, 103 | +5.0 |

Archives scanned: `terrain`, `foliage`, `tree`, `tileable`, `atlas`, `baked_props`, `trim`, `rocks`.
Only four entries exceeded a bias of 4, and `t_forest_ground_02` is the only strong one. The forest
sets -- not the grass sets -- are where the game's green actually lives.

**A second defect found while doing this:** base and detail were pointing at the *same file*, so one
texture was applied twice and the third family contributed nothing distinct. All three families are
now different textures:

```
base    forest/t_forest_ground_02/t_forest_ground_02_*    (green, RGB 121,124,97)
detail  grass/t_grass_02/t_grass_02_*                     (fine detail)
macro   forest/t_macro_forest/t_macro_forest_*            (large-scale mixing)
```

## 17. Floating towers: the west_coast shapes are unusable

The `west_coast_usa` building shapes have mesh origins hundreds of metres from their geometry:

```
city_west2.dae        centre (-844.71,  89.96)
city_block3.dae       centre (-322.53, 129.05)
condo_cylindrical.dae centre (-305.28, 115.46)
```

Placing one at a CS1 position therefore puts the visible mesh a long way from the placement point --
floating high above the map, exactly as observed. `city_block3` additionally measures **6.3x** the
size its table entry claims, confirming its geometry carries node transforms this measurement cannot
resolve.

They are **removed from the model set**. Buildings now use only the seven Italy industrial shapes,
whose origins sit within a few metres of their geometry. Of the 1,463 buildings:

```
ind_bld_12x30   1003      ind_bld_12x24     47
ind_bld_12x15    198      ind_bld_8x8       90
ind_bld_24x60    125
```

## 18. Building/road clearance

`BUILDING_ROAD_CLEARANCE` raised 1.25 -> **2.5 m**. Measured against the emitted road corridors with
the corrected rotation:

```
buildings sampled    1463
OVERLAPPING roads       0
tightest clearance  -1.648 m (bounding circle) / 0 overlapping (rotated rectangle)
```

The two closest buildings are held at the clearance limit; `b_17000` and `b_41773` are shrunk by the
rule rather than nudged, which is the intended behaviour when a footprint cannot be moved far enough
without relocating it arbitrarily.

**One caveat worth recording:** the shapes are multi-mesh and include trim, awnings and rooftop
details that extend past the main mass (`ind_bld_12x30`'s meshes range from 30.0 to 30.22 m). The
footprint test uses the shape's declared size, so a protrusion beyond it is not accounted for. The
measured clearance is therefore a lower bound on the true gap, not an exact figure.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended sections 16-18; document is now", len(text.split("\n")), "lines")
