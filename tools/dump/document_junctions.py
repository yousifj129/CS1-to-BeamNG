"""Document the junction root cause -- the most significant fix of the session."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 12. THE JUNCTION BUG -- roads never actually met

This is the real cause of "the roads are not connected", and it had been present from the first
version. Three separate earlier hypotheses were wrong before this was measured.

### 12.1 What the source data says

Nodes shared by two roads agree to **0.000 m**:

| Test | Result |
|---|---|
| Roads | 2,307 |
| Distinct node ids | 2,257 |
| Shared nodes whose endpoints disagree by >1 m | **0** |
| Maximum disagreement at a shared node | **0.000 m** |

So the topology is exact. Whatever the discontinuity was, it was introduced by the converter.

### 12.2 What the emitted level said

Measured on the built archive, before the fix:

| Test | Result |
|---|---|
| Junction nodes (>=3 roads) | 111 |
| Junction nodes with a chain endpoint on them | **0 / 111** |
| Chain endpoints within 1 m of a junction | **0 / 346** |
| Closest endpoint to its junction | 2.00 m |
| Median endpoint-to-junction distance | 10.00 m |
| Endpoints within 5 m of another chain's centre-line | **0 / 346** |

100% of junctions were unjoined. Not a rendering artefact and not a fade setting -- the geometry
genuinely stopped short everywhere.

### 12.3 The cause

`Road.surface_polyline` averaged the NODE elevation with the BEZIER elevation at the first and last
point, but kept the **Bezier's x/z**:

```python
points[0] = Vec3(first.x, (first.y + self.start_position.y) * 0.5, first.z)
#                 ^^^^^^^ Bezier x                                  ^^^^^^^ Bezier z
```

Its own docstring had the answer all along:

> on 259 segments (mostly Basic Road) its endpoints are pulled along the segment to handle junction
> corners

CS1 pulls Bezier endpoints *inward* at junction corners. The elevation average was added to cancel a
different, unrelated bias (+1.000 m on 1040 segments, -0.300 m on 326) and the x/z were left from the
Bezier -- so every road stopped exactly where CS1 pulled it in. The mean shortfall was 10 m, which is
precisely a junction corner radius.

### 12.4 The fix, and its result

The first and last point now take the **node's x/z**, with the elevation still averaged:

| Test | Before | After |
|---|---|---|
| Junction nodes with a chain endpoint on them | 0 / 111 | **111 / 111** |
| Endpoints sitting exactly on a junction | 0 / 346 | **286 / 346** |
| Endpoints within 0.01 m of another chain | 0 / 346 | **286 / 346** |
| Endpoints landing within the other chain's half-width | 1 / 346 | **287 / 346** |

The remaining 60 endpoints are genuine dead ends at the map edge, not failures.

### 12.5 A wrong fix that had to be reverted

Before finding this, an extension was added that pushed each chain end outward along its own
direction to force overlap. Measuring it showed **zero** coincident endpoint locations: at a
junction the meeting chains approach from *different* directions, so extending both moves their
ends **apart** -- up to 24 m at a right angle. Overshooting only helps two collinear segments, which
is not what a junction is. It was reverted, and the helper deleted so it cannot return.

### 12.6 The pattern, stated plainly

This is the fourth time in this session that a docstring or comment in the code contained the
information needed to find the bug, and the bug was in the line directly beneath it. The others
were the `.ter` `layerTextureMap`, the `soil/` vs `rock/` path, and the `_smooth` axis swap. Every
one was found by measuring the output rather than reasoning about the code.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 12; document is now", len(text.split("\n")), "lines")
