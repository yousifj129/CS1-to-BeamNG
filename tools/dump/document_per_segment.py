"""Document the junction fix via per-segment emission and the grass colour change."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 13. The remaining road gaps: chaining was the cause

After snapping chain endpoints to their nodes (section 12), 83% of endpoints joined and 111 of 111
junctions were covered -- but visible gaps remained, and the user's description pinpointed them:
*"some roads still have a gap... not an intersection"*.

### 13.1 The clue that solved it

> "the gravel/mud texture is perfectly outline all the roads, but the road on top of it is very
> unreliable"

The gravel is the painted terrain surface; the road is the `DecalRoad` on top. Both are generated
from the **same** source list, and measurement confirms chaining consumes **1,244 / 1,244** segments
-- nothing is dropped. So the loss had to be in the *geometry*, not the topology.

### 13.2 Why chaining breaks the middle of a road

Snapping fixed a chain's two ENDS. Inside a chain, consecutive source segments meet at a node, but
each segment's interior points come from **its own Bezier**, and CS1 offsets those. So at every
internal join the polyline can kink or step -- and unlike the chain ends, nothing snaps it. The
longer the chain, the more such joins: the median chain is 176 m and the longest **26.4 km**, from 96
segments.

That matches the symptom exactly: breaks *along* roads, not only at intersections.

### 13.3 Per-segment emission, measured against chaining

| | chained | per segment |
|---|---|---|
| DecalRoads | 173 | 1,244 |
| Endpoints landing on another road | 286 / 346 (**83%**) | **2,481 / 2,488 (99.7%)** |
| Median endpoint gap | 0.0000 m | 0.0000 m |
| **p90 endpoint gap** | **33.5 m** | **0.0000 m** |
| Worst gap | 224 m | 96 m |

The **p90** is the number that matters. In chained mode a tenth of all endpoints were more than
33 m from any other road; per-segment puts a node at every join, so the whole network closes at
0.0000 m. The remaining 7 endpoints are genuine dead ends.

Per-segment is now the default; `--chain-roads` opts back in for comparison.

This also matches the reference map, which the chaining decision had contradicted all along:
polish_roads_v2 ships 6,740 DecalRoads with a **median node count of 3**, and **42.1% of them are
two-node roads**. It uses short decals, not long chained polylines. The original reasoning -- that
short decals cause gaps and chaining would fix them -- was backwards.

### 13.4 Grass colour

The washed-out ground is the texture **blend strengths**, not the texture. `baseColorDetailStrength`
and `baseColorMacroStrength` are `[far, near]` pairs governing how strongly each family mixes over
the base; both were low, so the pale base tile dominated.

| | before | now |
|---|---|---|
| `baseColorDetailStrength` | `[0.4, 0.45]` | `[0.85, 0.95]` |
| `baseColorMacroStrength` | `[0, 0.1]` | `[0.5, 0.7]` |
| base tile | 2 m | 2 m |
| macro tile | 0.5 m | 1 m |
| detail tile | 0.25 m | 0.5 m |

The tile hierarchy was also reordered: detail must be finer than macro, which must be finer than
base. A conformance rule asserts that ordering, which is how the 1.0/0.5 inversion was caught.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 13; document is now", len(text.split("\n")), "lines")
