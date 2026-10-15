"""Document the overlap, grass and building-clearance fixes."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 14. Hairline decal seams, grass colour, and buildings on roads

### 14.1 Hairline seams: decals that touch still show a break

With one decal per segment, consecutive decals share an endpoint **exactly** (section 13). The user
found in the editor that nudging a decal along its own axis closed the visible gap, so the problem is
that two decals which merely *touch* still show a seam -- each has its own edge, and at the join there
is a break.

Each decal's two ends are now extended along its own local direction by `ROAD_DECAL_OVERLAP`, default
**1.0 m**. That value is the tunable knob: raise it if seams persist, lower it if joins look bloated.

This is deliberately **not** the extension that failed in section 12.5. That one pushed junction ends
by up to 12 m, and made things worse because chains meeting at a junction approach from different
directions -- extending both moved their ends *apart*. This one is a metre, applied at every join, and
its purpose is to make touching decals overlap rather than to bridge an angle.

### 14.2 Grass colour: the blend strengths, then the texture

The washed-out ground had two causes.

**Blend strengths.** `baseColorDetailStrength` and `baseColorMacroStrength` are `[far, near]` weights
for how strongly each family mixes over the base tile. Both were low, so the pale base dominated:

| | before | now |
|---|---|---|
| `baseColorDetailStrength` | `[0.4, 0.45]` | `[0.85, 0.95]` |
| `baseColorMacroStrength` | `[0, 0.1]` | `[0.5, 0.7]` |

**Texture choice.** The detail family carries most of the close-range colour, and it was set to
`ind_grass`, which measures a flat neutral grey (mean RGB **127, 127, 127**). It is now
`t_dirt_vegetation`, which is more saturated. Measured means from `terrain.zip`:

| set | mean RGB |
|---|---|
| `ind_grass` | 127, 127, 127 (neutral) |
| `t_grass_01` | 124, 124, 124 |
| `t_grass_02` | 111, 113, 107 |
| `t_macro_grass` | 110, 110, 110 |
| `t_dirt_vegetation` | *used for detail* |

Tile hierarchy was also corrected to detail < macro < base (0.5 / 1.0 / 2.0 m); an inversion was
caught by the conformance rule.

### 14.3 Buildings on roads

Placement sampled only the terrain under the footprint, so nothing considered the roads at all.
Measured on the built level: **56 of 1,463** buildings had a footprint overlapping a road, the worst
by 10.0 m.

The first fix -- capping the scale by distance to the road -- changed almost nothing, and tracing one
case showed why:

```
b_806   prefab "Road Connection"
nearest centre-line point = (8648.80, 343.43)   half-width 14.00   raw distance 0.00
best_edge = -14.0000        direction length = 0.0000
```

CS1 places "Road Connection" and "Water Pipe Junction" prefabs with their centre **exactly on a road
centre-line**. Scaling cannot fix that -- a footprint cannot be shrunk out of a corridor it is
centred in, and at -14 m the required scale is negative. So there is no direction "away" to use
either.

Three successive corrections were needed, each found by measuring the built output:

1. **Normal fallback.** When the centre is exactly on the centre-line, "away" is undefined; the
   segment normal is used, and whichever side ends up clearer wins (the other may be another
   carriageway).
2. **One uniform rule.** The shrink and push paths had been comparing different quantities. Now a
   single value decides: `effective = centre_edge - half_diagonal - clearance`. Negative means act:
   shrink if the centre is clear, push if it is not.
3. **Iteration, then a measured recheck.** A single push moved the right *distance* (7.969 m) in a
   direction that left the footprint 4.17 m inside the road it was moving away from, so the push
   repeats until it stops improving. A final recheck then measures the landed clearance and shrinks
   by any remaining shortfall -- necessary because the model's half-diagonal is not the CS1
   footprint the scale came from.

Result: **56 -> 0** overlapping, tightest clearance **+1.25 m** (`BUILDING_ROAD_CLEARANCE`).

The check itself also had to be strengthened. A rotated-corner test **under-reports** when the
model's own axes differ from the TSStatic rotation -- one building passed a corner test while still
4.17 m inside a road. The conformance report now tests a **bounding circle**, which is conservative
whatever the rotation, and that is the measure reported above.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 14; document is now", len(text.split("\n")), "lines")
