"""Document the fog, smoothing and tile-scale findings."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 11. The whitish wash, texture scale, terrain smoothness, and a hidden `_smooth` bug

### 11.1 The whitish filter was the template level's fog

The lighting block is copied from `levels/template`, which ships a much foggier and more tinted
atmosphere than any working map:

| | `fogColor` | `fogDensity` | `visibleDistance` |
|---|---|---|---|
| `levels/template` | `[0.741, 0.816, 0.925]` | **6.0e-4** | 4500 |
| `polish_roads_v2` | `[1, 1, 1]` | **2.8e-4** | 9000 |

The template's density is more than **twelve times** the working value and its colour is a strong
pale blue-grey. Together they wash the entire scene toward white/blue, which reads as a filter over
everything rather than as fog.

The `LevelInfo` clone now overrides all four values to the working map's, plus `decalBias 0.001`.
Note the template ships **two** `LevelInfo` objects with the *same* `persistentId` and different fog
densities (6.0e-4 and 8.0e-4) in two different files -- another reason to override rather than trust
what is copied.

### 11.2 `_smooth` silently changed the array shape on every call

The separable box blur padded for its vertical pass and then sliced **columns** instead of rows:

```python
np.pad(horizontal, 1, mode="edge")[0:-2, :]     # cuts rows, keeps the padded width
```

`horizontal` is already h x w, so padding makes it (h+2, w+2) and `[0:-2, :]` leaves **(h, w+2)** --
two columns too wide and two rows lost. Measured directly:

```
in (2048, 2048) -> out (2048, 2052)
in (100, 100)   -> out (94, 100)
in (7, 9)       -> out (1, 9)
```

This had been there from the beginning and never surfaced, because **every** caller passed the
result through `_as_square`, which crops silently. The only visible symptom was a slight edge
smear. It became a hard error only when the new coarse smoothing blended two grids and
`(2048, 2054)` could not be added to `(2048, 2048)`.

Both passes are now written explicitly with the padded axis named, and the output shape is asserted
against the input for several sizes including degenerate ones.

### 11.3 Terrain smoothness

Steep facets come from `_fill_gaps` interpolating across the sparse gaps between road samples.
`_smooth` is a 3x3 kernel, so three iterations reach about three cells -- roughly 12 m here -- which
removes local noise and does nothing about the long ramps.

Smoothing now runs at two scales: the existing fine pass, plus a coarse pass that downsamples by 4
(so each step covers 16x the ground), smooths, and upsamples back. The coarse result is blended at
0.65 so real elevation differences survive rather than being flattened to a plane.

**Measured:** mean neighbour step **2.63**, median **0**, p99 **15** (u16 units over `maxHeight`).
The maximum is 17,526 -- one isolated cliff, 0.0002% of cells. Worth investigating separately; it is
not representative.

### 11.4 Texture scale

The sets are 1024x1024, so tile size in metres sets the texel size directly:

| | before | now | texel |
|---|---|---|---|
| base | 8 m | **2 m** | 1.95 mm |
| macro | 2 m | **0.5 m** | 0.49 mm |
| detail | 0.5 m | **0.25 m** | 0.24 mm |

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 11; document is now", len(text.split("\n")), "lines")
