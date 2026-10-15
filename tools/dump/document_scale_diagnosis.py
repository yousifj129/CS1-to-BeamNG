"""Document the scale diagnosis and the corrected tile rules."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 21. Dark, bluish, oversaturated ground: it was the tile scale, not the strengths

The ground came out dark, blue-cast and magenta-flecked instead of green. The cause was the base
tile at **200 m**, and it acted through two mechanisms at once:

1. **Pixelation.** A 1024 px texture over 200 m puts ~20 cm of ground on each texel. The grass blades
   in `t_forest_ground_02`, drawn at centimetre scale, were magnified into large smears, and its tiny
   pink and magenta flecks became visible blotches.

2. **Magnified normals.** The base normal map is sampled with the same tile as the base colour, so a
   200x stretch magnifies every bump by 200x. The shading was then dominated by normal detail at a
   scale no eye reads as grass, which is what produced the dark, blue, over-processed look.

**The strengths were not the problem.** `normalDetailStrength [1, 0.3]` and
`normalMacroStrength [0.5, 0.5]` are polish_roads_v2's own Grass values. The mistake was scale.

### Why the reference can stretch its base and this level cannot

polish_roads_v2's Grass base tile is **2048 m**, and it looks right -- because its base image is a
**satellite photograph** of the whole map. A photograph has no usable close-range normal detail, so
magnifying it costs nothing. `t_forest_ground_02` is a close-up grass texture whose normal map is
full of structure; stretching it 200x is what broke the shading. **The reference's base *scale* is not
transferable, because the reference's base *asset* is a different kind of image.**

Its detail scale *is* transferable -- 3 m -- and is now used verbatim.

### Final values

| family | texture | tile | role |
|---|---|---|---|
| base | `forest/t_forest_ground_02` | **16 m** | colour |
| detail | `grass/t_grass_01` | **3 m** | fine variation (the reference's own figure) |
| macro | `grass/macro_grass` | **40 m** | large-scale variation |

`detailDistances [0, 0, 20, 40]` and `macroDistances [0, 0, 60, 300]` were also pulled in, so the
base hands over to the finer families sooner.

### The conformance rules were wrong too, and are corrected

They asserted `base >= 64 m` and `macro >= 32 m`, both taken from the reference's satellite-photo
base. That encoded the wrong model of what the base layer is. The rules now express what actually
matters:

* the base tiles between **8 and 64 m** -- legible, neither pixelated nor stretched;
* the detail between **0.5 and 12 m**;
* the macro coarser than the detail;
* base and detail are **different files** (an identical pair applies one map twice, which was a real
  defect found here).

A rule is only as good as the model behind it. This one had been carrying the satellite-photo
assumption since it was written.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 21; document is now", len(text.split("\n")), "lines")
