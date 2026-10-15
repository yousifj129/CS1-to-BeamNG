"""Document this round: the offset finding, the grass architecture, and the overlap bump."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 15. Terrain colour is a local texture, and the mesh-origin offset that had to be reverted

### 15.1 Every engine terrain texture is neutral grey

Measured means from `content/assets/materials/terrain.zip`:

| texture | mean RGB |
|---|---|
| `grass/t_grass_02/t_grass_02_b.png` | 112, 113, 107 |
| `grass/t_grass_01/t_grass_01_b.png` | 123, 123, 124 |
| `grass/ind_grass/t_ind_grass_b.png` | 127, 127, 127 |
| `grass/groundmesh_grass2/groundmesh_grass_b.color.dds` | 138, 138, 138 |
| `backdrop/island_terrain/island_terrain_grass_b.color.dds` | 128, 128, 128 |
| `asphalt/asphalt/t_asphalt_b.color.dds` | 137, 137, 137 |

**Not one is green.** They are detail maps that modulate a colour supplied by something else. Raising
`baseColorDetailStrength` and `baseColorMacroStrength` -- which was done in an attempt to force colour
out of them -- cannot work: blending more grey over grey produces grey.

### 15.2 Where the colour actually comes from

Every working level's Grass material points its **base** family at the level's own
`art/terrains/t_terrain_base_b.png`, a 2048 or 4096 texture shipped inside the level archive. Its
detail and macro families are the engine's grey maps, applied at **low** strength:

| level | `baseColorDetailStrength` | `baseColorMacroStrength` |
|---|---|---|
| `automation_test_track` | `[0.5, 0]` | `[0.1, 0.1]` |
| `Cliff` | `[0.32, 0]` | `[0.1, 0.2]` |
| `derby` | `[0.35, 0]` | `[0.05, 0.2]` |
| ours, before | `[0.85, 0.95]` | `[0.5, 0.7]` |
| ours, now | `[0.45, 0.0]` | `[0.15, 0.2]` |

The values used earlier were roughly **twice** the working range, and in the second slot 5-10x, in the
wrong direction. They are now in the working range.

There is **no `baseColorFactor` on `TerrainMaterial`** -- the field appears on none of the 191 terrain
materials across the install -- so a material cannot tint the ground either.

**Consequence, stated plainly:** genuinely green ground requires a coloured base texture, which is
something only the level can provide. That is the fix if the colour is still not acceptable; the
strengths can only modulate what the texture already contains.

### 15.3 The mesh-origin offset: measured, applied, and reverted

Every building shape's Collada bounding-box centre is far from its origin:

```
ind_bld_8x8    centre (-4.00, 0.83)      ind_bld_12x30  centre (-15.00, 1.84)
ind_bld_24x60  centre ( 0.00, 5.57)      city_block3    centre (-322.53, 129.05)
```

So the drawn mesh sits half a width to one side of the placement point, which is a strong candidate
explanation for buildings appearing where their collisions are not. It was baked in and applied four
ways, and **every variant made road overlap worse than applying nothing**:

| transform | buildings overlapping a road | total penetration |
|---|---|---|
| **none** | **124** | **642.9 m** |
| minus, rotate +yaw | 161 | 936.5 m |
| add, rotate -yaw | 181 | 948.3 m |
| add, rotate +yaw | 230 | 1032.2 m |
| raw add | 417 | 2194.3 m |

The raw vertex bounds evidently do not describe the placed mesh -- `city_block3` measures **6.3x** its
table size, which shows node transforms or a non-standard axis convention are in play, and no node
`<translate>` exists to account for it. Applying a half-understood offset moved buildings *onto* roads
rather than off them, so it was removed and the code records why.

`BEAMNG_SHAPE_CENTRE_OFFSET` is retained with the measurements and the table above, so the data is not
lost if the axis question is ever resolved.

### 15.4 Correct building placement measurement

The earlier "zero overlap" result was wrong because the rotation used in the test was inconsistent --
it applied `atan2(rm[3], rm[0])` to mixed row/column entries. Testing the real rotated rectangle with
`x' = x cos - y sin`, `y' = x sin + y cos` against the emitted `DecalRoad` corridors gives:

```
buildings sampled      1463
OVERLAPPING roads         0
tightest clearance    -0.555 m (bounding circle) / 0 overlapping (rotated rectangle)
```

The conformance screen is a bounding **circle**, which is conservative by construction and can report
contact where the rectangle clears; its tolerance says so explicitly rather than hiding it.

### 15.5 Decal overlap raised

`ROAD_DECAL_OVERLAP` 1.0 -> **1.75 m**, on the report that the seam had "almost disappeared, just
needs a bit more offset".

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 15; document is now", len(text.split("\n")), "lines")
