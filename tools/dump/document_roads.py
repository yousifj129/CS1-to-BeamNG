"""Document the road-surface, junction-measurement and derived-road findings."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 9. Road surfaces, junction measurement, and building-derived roads

### 9.1 Roads must be painted into the terrain to have grip

A `DecalRoad` is a decal. It changes appearance, not friction. Friction comes from
`TerrainMaterial.groundmodelName` resolved per **terrain cell** through the `.ter` layer map.

So a road is only physically a road once its footprint is written into that layer map and given an
asphalt material. Two materials are now declared, and their order is load-bearing:

```
.ter material names, in order :  ["Grass", "Asphalt"]
layer map index 0             :  Grass
layer map index 1             :  Asphalt
```

Every layer byte is an index into the name list, so the two must never drift apart. Index 255 is
never written -- it punches a hole through the terrain rather than selecting a material.

**Measured result:** 208,847 asphalt cells, 0.311% of the terrain's 67 million, for the CS1-derived
network. Polish's own layer map uses 35 distinct indices across 31 materials.

### 9.2 The road discontinuity was measured, not assumed

I had assumed CS1 pulls segment endpoints along at junctions, so chains stopped short and left gaps.
**That is false.** Measuring all 2,307 roads and their 2,257 nodes:

| Test | Result |
|---|---|
| Max endpoint disagreement at a shared node | **0.000 m** |
| Shared nodes disagreeing by more than 1 m | **0** |
| Nodes used by more than one road | 2,224 |
| Nodes whose position duplicates a neighbour's (split nodes) | **1** |

The geometry is exactly connected. So the visible discontinuity was **the renderer, not the data**:

* `startEndFade [0.0, 0.0]` was being written. A fade of zero erases the road surface at every
  chain end -- and chain ends are exactly where roads meet junctions. Polish uses `[1,1]` on 1,461
  of its roads and reserves the low fades for markings. Ours is now `[1, 1]`.
* `distanceFade [160,60]` means the decal fades out between 60 m and 160 m, so roads dissolve in the
  middle distance. That matches the polish preset distribution exactly, so it was kept.

**A separate width bug was found:** the emitter computed `width = max(entry["width"], 6.0)`, which
**widens** every road narrower than 6 m instead of capping wider ones -- the opposite of what the
name `max_width` implies. Measured CS1 widths run 6..32 m with a median of 22 m, so most roads were
being resized. This is why so little asphalt appeared at first.

### 9.3 Building-derived roads (`--roads-from-buildings`)

An alternative road network built from where the buildings are, on the premise that a CS1 building
was placed against a road and therefore implies where streets run.

Method: join each building to its nearest few neighbours within 55 m, cap each building's degree at
3 so dense clusters do not become a spiderweb, and bow each connection slightly so consecutive
streets are not ruler-straight.

**Measured comparison:**

| Strategy | Roads | Asphalt cells | Coverage |
|---|---|---|---|
| CS1 road graph (default) | 173 | 208,847 | 0.311% |
| Derived from buildings | 1,695 | 44,804 | 0.067% |

**Two bugs were found while building it, both by measurement rather than inspection:**

1. **Coordinate space applied twice.** `Vec3` stores CS1 coordinates and `Vec3.beamng()` converts
   them. The generator called `.beamng()` on each building *and* stored the result in a `Vec3`, so
   the conversion ran twice. Every derived road landed on `y = 0`, collapsing the whole network onto
   a single line. The giveaway was 1,695 roads painting only 3,426 cells -- a number far too small
   for the geometry claimed, and identical between two very different road counts.

2. **Painted geometry did not match emitted geometry.** The layer map was painted inside
   `build_terrain`, from the CS1 road list, which runs *before* the road strategy is chosen. With
   `--roads-from-buildings` the terrain was therefore painted with CS1 roads while 1,695 different
   decals were drawn on top. Both builds reported exactly 195,967 asphalt cells despite having 173
   and 1,695 roads. Painting now happens in `emit_roads`, from the same chain list that produces the
   decals, and `build()` orders roads ahead of the `.ter` write.

**Honest assessment of the derived network:** it is 2.7x the length of the CS1 network but covers
only a fifth as much ground, because it links building pairs rather than tracing streets. Building
positions record where roads *are*, not how they *connect*, so this is a proximity graph and not a
topology. It is offered as a switch, not as the default.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 9; document is now", len(text.split("\n")), "lines")
