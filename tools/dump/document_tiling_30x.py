"""Document the 30x grass tiling reduction and the rule it corrected."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 23. Grass tiling reduced 30x, and the family ordering it broke

Base tile reduced from 32 m to **1.07 m**, a factor of 30, on request. At 1024 px that is about
**1 mm per texel**, so the texture's own pixels are far below the visible threshold and the blades
read at their intended size rather than being magnified.

The change broke a relationship that had to be fixed with it: the detail layer was tiled at 3 m --
**coarser than the 1.07 m base it exists to detail**, which is backwards. All three families were
scaled proportionally:

| family | before | now | texel |
|---|---|---|---|
| base | 32 m | **1.07 m** | 1.04 mm |
| detail | 3 m | **0.35 m** | 0.34 mm |
| macro | 40 m | **3 m** | 2.93 mm |

`detail < base < macro` now holds, which is the ordering that matters.

### A conformance rule was wrong again, for an instructive reason

The detail rule asserted an **absolute** range of 0.5-12 m, justified by "the reference's grass uses
3 m". That figure is only meaningful relative to the reference's own base, which is 2048 m -- its
detail is about **680x finer** than its base. An absolute floor becomes meaningless the moment the
base changes scale: against a 1.07 m base, a 3 m "detail" layer is simply wrong.

The rule is now **relative** -- the detail must tile finer than the base, with only a sanity floor
(0.05 m) beneath it.

This is the third rule in this project found to encode an assumption copied from the reference that
did not transfer, after the `base >= 64 m` rule and the "all 15 textures from the engine" rule.
**A value taken from a working example is only valid together with the conditions that made it work.**

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 23; document is now", len(text.split("\n")), "lines")
